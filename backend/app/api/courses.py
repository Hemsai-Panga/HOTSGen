"""Public student API routes for course browsing and syllabus topic hierarchy retrieval."""

from typing import List
from fastapi import APIRouter, HTTPException, Query, status

from app.models.course import CoursePublicResponse, PublicSyllabusResponse
from app.services.course_service import (
    CourseNotFoundError,
    CourseService,
    DatabaseUnavailableError,
)
from app.services.syllabus_service import SyllabusService

router = APIRouter()


@router.get(
    "",
    response_model=List[CoursePublicResponse],
    summary="List Courses (Student)",
    description="Public endpoint for students to browse all available university courses.",
)
def list_courses(
    skip: int = Query(0, ge=0, description="Pagination skip offset"),
    limit: int = Query(100, ge=1, le=100, description="Pagination limit"),
) -> List[CoursePublicResponse]:
    """Retrieve public list of courses without exposing internal administrative metadata."""
    try:
        courses = CourseService.list_courses(skip=skip, limit=limit)
        return [
            CoursePublicResponse(
                course_code=c.course_code,
                course_name=c.course_name,
                description=c.description,
                units=c.units,
            )
            for c in courses
        ]
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please try again later.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing courses: {type(e).__name__}",
        )


@router.get(
    "/{course_code}",
    response_model=CoursePublicResponse,
    summary="Get Course Details (Student)",
    description="Public endpoint to get syllabus details and description for a specific course.",
)
def get_course_public(course_code: str) -> CoursePublicResponse:
    """Retrieve public details for a course by course code."""
    try:
        course = CourseService.get_course(course_code)
        return CoursePublicResponse(
            course_code=course.course_code,
            course_name=course.course_name,
            description=course.description,
            units=course.units,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_code.strip().upper()}' not found",
        )
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please try again later.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the course: {type(e).__name__}",
        )


@router.get(
    "/{course_code}/topics",
    response_model=PublicSyllabusResponse,
    summary="Get Course Topics Hierarchy (Student)",
    description="Public endpoint for students to retrieve the structured unit -> topic -> subtopic syllabus hierarchy.",
)
def get_course_topics_public(course_code: str) -> PublicSyllabusResponse:
    """Retrieve structured syllabus hierarchy for a course with zero authentication."""
    try:
        syllabus = SyllabusService.get_course_syllabus(course_code)
        return syllabus
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_code.strip().upper()}' not found",
        )
