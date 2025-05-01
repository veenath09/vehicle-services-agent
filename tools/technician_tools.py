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
