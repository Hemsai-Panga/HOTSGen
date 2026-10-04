"""Developer course management API routes."""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import get_current_developer
from app.models.course import (
    CourseAdminResponse,
    CourseCreate,
    CourseUpdate,
)
from app.services.course_service import (
    CourseAlreadyExistsError,
    CourseNotFoundError,
    CourseService,
    DatabaseUnavailableError,
)

router = APIRouter(dependencies=[Depends(get_current_developer)])


@router.post(
    "",
    response_model=CourseAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Course (Developer)",
    description="Developer endpoint to register a new course record.",
)
def create_course(
    course_in: CourseCreate,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> CourseAdminResponse:
    """Create a new course record with unique course_code."""
    try:
        created = CourseService.create_course(course_in)
        return CourseAdminResponse(
            id=created.id,
            course_code=created.course_code,
            course_name=created.course_name,
            description=created.description,
            units=created.units,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )
    except CourseAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except DatabaseUnavailableError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check database connection.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while creating the course: {type(e).__name__}",
        )


@router.get(
    "",
    response_model=List[CourseAdminResponse],
    summary="List Courses (Developer)",
    description="Developer endpoint to view all courses with administrative metadata.",
)
def list_courses_developer(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> List[CourseAdminResponse]:
    """List all courses with administrative metadata."""
    try:
        courses = CourseService.list_courses(skip=skip, limit=limit)
        return [
            CourseAdminResponse(
                id=c.id,
                course_code=c.course_code,
                course_name=c.course_name,
                description=c.description,
                units=c.units,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in courses
        ]
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check database connection.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing courses: {type(e).__name__}",
        )


@router.get(
    "/{course_code}",
    response_model=CourseAdminResponse,
    summary="Get Course (Developer)",
    description="Developer endpoint to fetch details of a specific course.",
)
def get_course_developer(
    course_code: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> CourseAdminResponse:
    """Fetch specific course by course code."""
    try:
        course = CourseService.get_course(course_code)
        return CourseAdminResponse(
            id=course.id,
            course_code=course.course_code,
            course_name=course.course_name,
            description=course.description,
            units=course.units,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_code.strip().upper()}' not found",
        )
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check database connection.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching the course: {type(e).__name__}",
        )


@router.put(
    "/{course_code}",
    response_model=CourseAdminResponse,
    summary="Update Course (Developer)",
    description="Developer endpoint to update course name and description (course code is immutable).",
)
def update_course_developer(
    course_code: str,
    course_update: CourseUpdate,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> CourseAdminResponse:
    """Update course metadata."""
    try:
        updated = CourseService.update_course(course_code, course_update)
        return CourseAdminResponse(
            id=updated.id,
            course_code=updated.course_code,
            course_name=updated.course_name,
            description=updated.description,
            units=updated.units,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{course_code.strip().upper()}' not found",
        )
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check database connection.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while updating the course: {type(e).__name__}",
        )


@router.delete(
    "/{course_code}",
    summary="Delete Course (Developer)",
    description="Developer endpoint to delete a course and its knowledge base association.",
)
def delete_course_developer(
    course_code: str,
    current_developer: Dict[str, Any] = Depends(get_current_developer),
) -> Dict[str, str]:
    """Delete a course record."""
    normalized_code = course_code.strip().upper()
    try:
        CourseService.delete_course(normalized_code)
        return {
            "status": "success",
            "message": f"Course '{normalized_code}' deleted successfully",
        }
    except CourseNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course '{normalized_code}' not found",
        )
    except DatabaseUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database service unavailable. Please check database connection.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not delete course: {type(e).__name__}",
        )
