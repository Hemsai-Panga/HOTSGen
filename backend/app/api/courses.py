"""Public student API routes for course browsing."""

from typing import List
from fastapi import APIRouter, HTTPException, Query, status

from app.models.course import CoursePublicResponse
from app.services.course_service import CourseNotFoundError, CourseService

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
