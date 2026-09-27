"""
Pulsarr - Book Model

This module defines the Book data model.

A Book represents a single item in the user's wishlist.

The model only describes the data structure.

Currently:
- Title
- Author
- Series
- Series number
- Status

Future Enhancements for the total book library:

- Location (on disk)
- Rating
- Date added
- Description

"""

from sqlmodel import Field, SQLModel
from src.models.enums import Status

class Book(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)

    title: str
    author: str

    status: Status = Field(default=Status.UNAVAILABLE)