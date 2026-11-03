# AWS Serverless Ticket Management System

A serverless ticket management backend built using AWS services and Python.

## Project Overview

This project provides REST APIs to manage support tickets using AWS Lambda, API Gateway, and Amazon RDS. It also sends email notifications whenever a critical-priority ticket is created.

## Technologies Used

- AWS Lambda (Python 3.12)
- Amazon API Gateway
- Amazon RDS (MySQL)
- AWS Secrets Manager
- Amazon SNS
- Postman

## Architecture

User / Postman → API Gateway → AWS Lambda

AWS Lambda connects to:
- Amazon RDS for ticket data storage
- AWS Secrets Manager for secure database credentials
- Amazon SNS for critical ticket email notifications

## Features

- Create new tickets
- Retrieve all tickets
- Update existing tickets
- Delete tickets
- Store ticket information in MySQL
- Secure database credentials using Secrets Manager
- Send email alerts for critical tickets
- Test REST APIs using Postman

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | /tickets | Retrieve tickets |
| POST | /tickets | Create a ticket |
| PUT | /tickets/{id} | Update a ticket |
| DELETE | /tickets/{id} | Delete a ticket |

## Database

- Database: MySQL
- Table: tickets
- Hosted on Amazon RDS

## Notifications

Amazon SNS sends an email notification when a ticket with CRITICAL priority is created.

## Testing

All CRUD API operations and critical-ticket email notifications were tested successfully using Postman.

## Future Improvements

- API authentication and authorization
- Improved security and access controls
- Architecture documentation

## Author

Akshada Rathod

GitHub: [akshadar6825](https://github.com/akshadar6825)
