import json
import os
import boto3
import pymysql
from datetime import date, datetime
from decimal import Decimal

# AWS configuration
REGION = os.environ.get("REGION_NAME", "ap-south-1")
SECRET_NAME = os.environ["SECRET_NAME"]
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

secrets_client = boto3.client("secretsmanager", region_name=REGION)
sns_client = boto3.client("sns", region_name=REGION)


def response(status_code, message, **extra):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
        },
        "body": json.dumps(
            {"message": message, **extra},
            default=json_serializer
        )
    }


def json_serializer(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def get_db_credentials():
    secret = secrets_client.get_secret_value(
        SecretId=SECRET_NAME
    )
    return json.loads(secret["SecretString"])


def get_db_connection():
    credentials = get_db_credentials()

    host = credentials.get("host") or credentials.get("endpoint")
    username = credentials.get("username") or credentials.get("user")
    password = credentials["password"]

    if not host or not username:
        raise Exception("Database host or username missing in secret")

    # Create database if it does not exist
    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with connection.cursor() as cursor:
            cursor.execute("CREATE DATABASE IF NOT EXISTS ticket_db")
    finally:
        connection.close()

    # Connect to ticket_db
    connection = pymysql.connect(
        host=host,
        user=username,
        password=password,
        database="ticket_db",
        connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

    # Create tickets table if it does not exist
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                priority VARCHAR(20) DEFAULT 'LOW',
                status VARCHAR(20) DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    connection.commit()

    return connection


def lambda_handler(event, context):
    connection = None

    try:
        method = event.get("httpMethod", "")
        path_parameters = event.get("pathParameters") or {}
        ticket_id = path_parameters.get("id")

        if method == "OPTIONS":
            return response(200, "CORS request successful")

        connection = get_db_connection()

        with connection.cursor() as cursor:

            # GET: Fetch all tickets
            if method == "GET":
                cursor.execute(
                    "SELECT * FROM tickets ORDER BY id DESC"
                )
                tickets = cursor.fetchall()

                return response(
                    200,
                    "Tickets fetched successfully",
                    total=len(tickets),
                    tickets=tickets
                )

            # POST: Create a new ticket
            elif method == "POST":
                body = json.loads(event.get("body") or "{}")

                title = body.get("title")
                description = body.get("description", "")
                priority = body.get("priority", "LOW").upper()
                status = body.get("status", "OPEN").upper()

                if not title:
                    return response(400, "Title is required")

                if priority not in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
                    return response(400, "Invalid priority")

                if status not in ["OPEN", "IN_PROGRESS", "RESOLVED"]:
                    return response(400, "Invalid status")

                cursor.execute("""
                    INSERT INTO tickets
                    (title, description, priority, status)
                    VALUES (%s, %s, %s, %s)
                """, (title, description, priority, status))

                new_ticket_id = cursor.lastrowid
                connection.commit()

                # Send SNS notification for CRITICAL tickets
                if priority == "CRITICAL" and SNS_TOPIC_ARN:
                    sns_client.publish(
                        TopicArn=SNS_TOPIC_ARN,
                        Subject="Critical Ticket Alert",
                        Message=(
                            f"New CRITICAL ticket created.\n"
                            f"Ticket ID: {new_ticket_id}\n"
                            f"Title: {title}\n"
                            f"Description: {description}"
                        )
                    )

                return response(
                    201,
                    "Ticket created successfully",
                    ticket_id=new_ticket_id,
                    priority=priority
                )

            # PUT: Update an existing ticket
            elif method == "PUT":
                if not ticket_id:
                    return response(400, "Ticket ID is required")

                body = json.loads(event.get("body") or "{}")

                allowed_fields = [
                    "title", "description", "priority", "status"
                ]

                update_fields = {
                    key: value
                    for key, value in body.items()
                    if key in allowed_fields
                }

                if not update_fields:
                    return response(400, "No valid fields provided")

                if "priority" in update_fields:
                    update_fields["priority"] = str(
                        update_fields["priority"]
                    ).upper()

                    if update_fields["priority"] not in [
                        "LOW", "MEDIUM", "HIGH", "CRITICAL"
                    ]:
                        return response(400, "Invalid priority")

                if "status" in update_fields:
                    update_fields["status"] = str(
                        update_fields["status"]
                    ).upper()

                    if update_fields["status"] not in [
                        "OPEN", "IN_PROGRESS", "RESOLVED"
                    ]:
                        return response(400, "Invalid status")

                if "title" in update_fields and not update_fields["title"]:
                    return response(400, "Title cannot be empty")

                set_clause = ", ".join(
                    f"`{field}` = %s"
                    for field in update_fields
                )

                values = list(update_fields.values())
                values.append(ticket_id)

                cursor.execute(
                    f"UPDATE tickets SET {set_clause} WHERE id = %s",
                    values
                )

                if cursor.rowcount == 0:
                    cursor.execute(
                        "SELECT id FROM tickets WHERE id = %s",
                        (ticket_id,)
                    )

                    if not cursor.fetchone():
                        connection.rollback()
                        return response(404, "Ticket not found")

                connection.commit()

                return response(
                    200,
                    "Ticket updated successfully",
                    ticket_id=int(ticket_id),
                    updated_fields=list(update_fields.keys())
                )

            # DELETE: Delete an existing ticket
            elif method == "DELETE":
                if not ticket_id:
                    return response(400, "Ticket ID is required")

                cursor.execute(
                    "DELETE FROM tickets WHERE id = %s",
                    (ticket_id,)
                )

                if cursor.rowcount == 0:
                    connection.rollback()
                    return response(404, "Ticket not found")

                connection.commit()

                return response(
                    200,
                    "Ticket deleted successfully",
                    ticket_id=int(ticket_id)
                )

            else:
                return response(405, "Method not allowed")

    except Exception as error:
        print("ERROR:", str(error))

        if connection:
            connection.rollback()

        return response(500, "Internal server error")

    finally:
        if connection:
            connection.close()
