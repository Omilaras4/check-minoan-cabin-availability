import requests
import time
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import logging
import os
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

def check_availability(date, passengers):
    try:
        # API endpoint
        url = "https://www.minoan.gr/api/v2/trips"
        
        # Parameters for the request
        params = {
            "from": "PIR",
            "to": "HER",
            "departureDate": date,
            "numPass": passengers,
            "lang": "el"
        }
        
        # Headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
            'Referer': f'https://www.minoan.gr/booking?from=PIR&to=HER&date={date}&passengers={passengers}&pets=0&step=2&vehicles=0',
            'Origin': 'https://www.minoan.gr',
            'Accept-Language': 'en-US,en;q=0.9'
        }

        # Make the request
        logging.info(f"Making request to URL: {url}")
        logging.info(f"With parameters: {params}")
        response = requests.get(url, params=params, headers=headers)
        
        # Print response status and headers
        logging.info(f"Response status code: {response.status_code}")
        logging.info(f"Response headers: {dict(response.headers)}")
        
        # Print response content
        logging.info(f"Response content: {response.text[:500]}")  # Print first 500 chars of response
        
        if response.status_code == 200:
            data = response.json()
            logging.info("Successfully parsed JSON response")
            
            # Check if there are any trips
            if data and len(data) > 0 and 'trips' in data[0]:
                trip = data[0]['trips'][0]
                
                # Check cabin availability
                available_cabins = []
                if 'accommodations' in trip and 'passenger' in trip['accommodations']:
                    for acc in trip['accommodations']['passenger']:
                        if acc['code'] in ['AB3', 'A3','D'] and acc['wholeBerthAvailability'] > 0:
                            available_cabins.append({
                                'type': acc['name'],
                                'availability': acc['wholeBerthAvailability'],
                                'price': acc['price']
                            })
                
                if available_cabins:
                    send_notification(available_cabins, trip['departureDateTime'], date)
                    logging.info(f"Cabins found available for date: {date}")
                    return True
                
                logging.info(f"No cabins available for date: {date}")
            
        else:
            logging.error(f"Error in API request: {response.status_code}")
            logging.error(f"Error response: {response.text}")
            
        return False

    except json.JSONDecodeError as e:
        logging.error(f"JSON Decode Error: {str(e)}")
        logging.error(f"Response content that caused error: {response.text}")
        return False
    except Exception as e:
        logging.error(f"Error checking availability: {str(e)}")
        return False

def send_notification(available_cabins, departure_time, date):
    try:
        # Get email credentials from GitHub secrets
        email_sender = os.environ['EMAIL_SENDER']
        email_password = os.environ['EMAIL_PASSWORD']
        email_recipient = os.environ['EMAIL_RECIPIENT']
        passengers = int(os.environ['PASSENGERS'])

        # Create a detailed message
        message = f"Cabins have become available for your desired date: {date}\n"
        message += f"Departure time: {departure_time}\n\n"
        message += "Available cabins:\n"
        
        for cabin in available_cabins:
            message += f"- {cabin['type']}\n"
            message += f"  Price: €{cabin['price']}\n"
            message += f"  Available berths: {cabin['availability']}\n\n"
        
        message += f"\nBook now at: https://www.minoan.gr/booking?from=PIR&to=HER&date={date}"
        message += f"&passengers={passengers}&pets=0&step=2&vehicles=0"
        
        msg = MIMEText(message)
        msg['Subject'] = "Minoan Lines - Cabin Available!"
        msg['From'] = email_sender
        msg['To'] = email_recipient
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp_server:
            smtp_server.login(email_sender, email_password)
            smtp_server.sendmail(email_sender, email_recipient, msg.as_string())
        
        logging.info("Notification email sent successfully")
        
    except Exception as e:
        logging.error(f"Error sending notification: {str(e)}")

if __name__ == "__main__":
    logging.info("Script started")
    logging.info(f"Using date: {os.environ['SEARCH_DATE']}")
    logging.info(f"Using passengers: {os.environ['PASSENGERS']}")
    
    date = os.environ['SEARCH_DATE']
    passengers = int(os.environ['PASSENGERS'])
    check_availability(date, passengers)
