from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional, List, Any
from langchain_experimental.utilities import PythonREPL
from typing_extensions import TypedDict
from langchain_core.tools import tool
import json
from utils.database import get_db_connection
from datetime import datetime, time

@tool
def find_technicians(
    specializations: Optional[List[str]] = None,
    location: Optional[Dict[str, str]] = None,
    experience_years: Optional[int] = None,
    availability_days: Optional[List[str]] = None,
    min_rating: Optional[float] = None
) -> str:
    """
    Find technicians based on the user requested criteria provide an output even if a single criteria is given use that critiria to provide the output
    
    Args:
        specializations: List of specializations to filter by (e.g., ["Engine Repair", "Electrical Systems"])
        location: Dictionary with location details (e.g., {"city": "Colombo"})
        experience_years: Minimum years of experience required
        availability_days: List of required availability days (e.g., ["Monday", "Tuesday"])
        min_rating: Minimum average rating required
        
    Returns:
        JSON string with technician information
    """
    print("Finding technicians with the following criteria:")
    print(f"Specializations: {specializations}")
    print(f"Location: {location}")
    
    try:
        db = get_db_connection()
        technician_collection = db.technicians  # Adjust collection name if needed
        
        # Build query based on provided filters
        query = {}
        
        if specializations:
            query["specializations"] = {"$in": specializations}
        
        if location:
            for key, value in location.items():
                query[f"location.{key}"] = value
        
        if experience_years is not None:
            query["experience"] = {"$gte": experience_years}
        
        if availability_days:
            query["availability.daysOfWeek"] = {"$all": availability_days}
        
        if min_rating is not None:
            query["ratings.average"] = {"$gte": min_rating}
        
        # Find technicians matching the criteria
        technicians = list(technician_collection.find(query))
        
        # Convert ObjectId to string for JSON serialization
        for tech in technicians:
            if "_id" in tech:
                tech["_id"] = str(tech["_id"])
        
        if not technicians:
            return json.dumps({"message": "No technicians found matching the criteria.", "technicians": []})
        
        # Format the results
        result = {
            "message": f"Found {len(technicians)} technician(s) matching your criteria.",
            "technicians": technicians
        }
        
        return result
    
    except Exception as e:
        return json.dumps({"error": f"Error finding technicians: {str(e)}"})

@tool
def check_technician_availability(
    technician_id: str,
    date: str,
    time_slot: Optional[str] = None
) -> str:
    """
    Check if a technician is available on a specific date and time.
    
    Args:
        technician_id: The MongoDB ID of the technician to check
        date: The date to check availability for in format 'YYYY-MM-DD'
        time_slot: Optional time slot to check in format 'HH:MM' (24-hour format)
        
    Returns:
        JSON string with availability information
    """
    try:
        db = get_db_connection()
        reservations_collection = db.technicianreservations
        
        # Parse the date
        try:
            check_date = datetime.strptime(date, '%Y-%m-%d')
            # Set the time to midnight to compare only the date part
            start_of_day = datetime.combine(check_date.date(), time.min)
            end_of_day = datetime.combine(check_date.date(), time.max)
        except ValueError:
            return json.dumps({
                "error": f"Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-05-20)"
            })
        
        # Build the query
        query = {
            "technician": technician_id,
            "service.date": {
                "$gte": start_of_day,
                "$lte": end_of_day
            }
        }
        
        # Add time filter if provided
        if time_slot:
            query["service.time"] = time_slot
            
        # Find reservations for this technician on the specified date (and time if provided)
        reservations = list(reservations_collection.find(query))
        
        # Convert ObjectId to string for JSON serialization
        for res in reservations:
            if "_id" in res:
                res["_id"] = str(res["_id"])
            if "technician" in res:
                res["technician"] = str(res["technician"])
        
        # Determine availability
        is_available = len(reservations) == 0
        
        # Format the response
        if is_available:
            result = {
                "available": True,
                "message": f"Technician {technician_id} is available on {date}" + 
                          (f" at {time_slot}" if time_slot else ""),
                "reservations": []
            }
        else:
            result = {
                "available": False,
                "message": f"Technician {technician_id} is NOT available on {date}" + 
                          (f" at {time_slot}" if time_slot else "") + 
                          f". Found {len(reservations)} existing reservation(s).",
                "reservations": reservations if len(reservations) <= 5 else 
                                [res for res in reservations[:5]]  # Limit to 5 reservations in response
            }
            
            # If more than 5 reservations, add a note
            if len(reservations) > 5:
                result["message"] += " (Showing first 5 reservations)"
        
        return json.dumps(result)
    
    except Exception as e:
        return json.dumps({"error": f"Error checking technician availability: {str(e)}"})

@tool
def reserve_technician(
    technician_id: str,
    customer_name: str,
    customer_email: str,
    customer_contact: str,
    customer_user_id: str,
    vehicle_make: str,
    vehicle_model: str,
    vehicle_year: int,
    service_type: str,
    service_date: str,
    service_time: str,
    service_location: str,
    problem_description: str,
    additional_notes: Optional[str] = None
) -> str:
    """
    Reserve a technician for a specific service appointment. Request for missing information if any required information is missing 
    
    Args:
        technician_id: The MongoDB ID of the technician to reserve
        customer_name: Full name of the customer
        customer_email: Email address of the customer
        customer_contact: Contact number of the customer
        customer_user_id: User ID of the customer
        vehicle_make: Make/brand of the vehicle
        vehicle_model: Model of the vehicle
        vehicle_year: Manufacturing year of the vehicle
        service_type: Type of service requested
        service_date: Date for the service in format 'YYYY-MM-DD'
        service_time: Time for the service in 24-hour format 'HH:MM'
        service_location: Location where the service will be performed
        problem_description: Description of the problem or service needed
        additional_notes: Any additional information or special requests
        
    Returns:
        JSON string with reservation confirmation or error message
    """
    try:
        db = get_db_connection()
        technician_collection = db.technicians
        reservations_collection = db.technicianreservations
        
        # Validate technician exists
        technician = technician_collection.find_one({"_id": technician_id})
        if not technician:
            return json.dumps({
                "success": False,
                "error": f"Technician with ID {technician_id} not found."
            })
            
        # Parse the date
        try:
            service_datetime = datetime.strptime(service_date, '%Y-%m-%d')
        except ValueError:
            return json.dumps({
                "success": False,
                "error": f"Invalid date format. Please use YYYY-MM-DD format (e.g., 2025-05-20)"
            })
            
        # Check if technician is available at this time
        availability_check = check_technician_availability(technician_id, service_date, service_time)
        availability_result = json.loads(availability_check)
        
        if availability_result.get("error"):
            return json.dumps({
                "success": False,
                "error": availability_result["error"]
            })
            
        if availability_result.get("available") is False:
            return json.dumps({
                "success": False,
                "error": f"Technician is not available on {service_date} at {service_time}. Please choose another date/time."
            })
        
        # Create the reservation
        technician_name = technician.get("name", "Unknown")
        
        reservation = {
            "technician": technician_id,
            "technicianName": technician_name,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contactNumber": customer_contact,
                "userId": customer_user_id
            },
            "vehicle": {
                "make": vehicle_make,
                "model": vehicle_model,
                "year": vehicle_year
            },
            "service": {
                "type": service_type,
                "date": service_datetime,
                "time": service_time,
                "location": service_location,
                "problemDescription": problem_description,
                "additionalNotes": additional_notes or ""
            },
            "status": "Pending",
            "createdAt": datetime.now(),
            "updatedAt": datetime.now()
        }
        
        # Insert reservation into database
        result = reservations_collection.insert_one(reservation)
        
        if result.inserted_id:
            return json.dumps({
                "success": True,
                "message": f"Reservation successfully created for {customer_name} with technician {technician_name}.",
                "reservation_id": str(result.inserted_id),
                "details": {
                    "technician": technician_name,
                    "date": service_date,
                    "time": service_time,
                    "service": service_type,
                    "location": service_location
                }
            })
        else:
            return json.dumps({
                "success": False,
                "error": "Failed to create reservation. Database error."
            })
            
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"Error creating reservation: {str(e)}"
        })
