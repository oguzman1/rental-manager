# Rental Manager

Backend API for managing rental properties, active rentals, and rent adjustment notices.

## What it does

This project allows a user to:

- create managed properties
- list stored properties
- update properties by id
- delete properties by id
- store active rental data
- track tenant name and payment day
- calculate upcoming rent adjustment dates
- calculate adjustment notice dates
- identify rentals that require adjustment notice

## Tech stack

- Python
- FastAPI
- Pydantic
- SQLite
- Pytest

## Current API

- `GET /health`
- `GET /managed-properties`
- `POST /managed-property`
- `PUT /managed-property/{property_id}`
- `DELETE /managed-property/{property_id}`
- `GET /rent-adjustments`

## Project structure

- `main.py` → API endpoints and business rules
- `models.py` → request/response models and enums
- `db.py` → SQLite connection and persistence logic
- `adjustments.py` → rent adjustment calculation logic
- `tests/` → automated tests

## Core concepts implemented

- request/response validation with Pydantic
- business rule validation
- SQLite persistence
- simple database migration handling
- tenant and payment day tracking
- rent adjustment date calculation
- adjustment notice calculation
- isolated test database
- basic automated API tests

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload