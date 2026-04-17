# Rental Manager

Backend API for managing rental properties and current rental data.

## What it does

This project allows a user to:

- create managed properties
- list stored properties
- update properties by id
- delete properties by id

It also validates:
- input structure
- business rules
- duplicate conflicts in persistence

## Tech stack

- Python
- FastAPI
- Pydantic
- SQLite

## Current API

- `GET /health`
- `GET /managed-properties`
- `POST /managed-property`
- `PUT /managed-property/{property_id}`
- `DELETE /managed-property/{property_id}`

## Project structure

- `main.py` → API endpoints and business rules
- `models.py` → request/response models and enums
- `db.py` → SQLite connection and persistence logic

## Run locally

1. Create and activate a virtual environment
2. Install dependencies
3. Start the server

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload