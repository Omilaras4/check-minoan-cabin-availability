import requests
from bs4 import BeautifulSoup
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

class MinoanSession:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        })

    def init_session(self):
        """Initialize session by visiting the main booking page first"""
        try:
            # First, visit the main booking page
            initial_url = "https://www.minoan.gr/booking"
            logging.info(f"Visiting initial page: {initial_url}")
            
            response = self.session.get(initial_url)
            logging.info(f"Initial page status: {response.status_code}")

            soup = BeautifulSoup(response.text, 'html.parser')
        
            # Look for CSRF token in meta tags or form fields
            csrf_token = soup.find('meta', {'name': 'csrf-token'})
            if csrf_token:
                headers['X-CSRF-TOKEN'] = csrf_token.get('content')
                logging.info(f"X-CSRF-TOKEN: csrf_token.get('content')")
            
            if response.status_code == 200:
                # Now visit the step 1 page
                step1_url = "https://www.minoan.gr/booking"
                params = {
                    "from": "PIR",
                    "to": "HER",
                    "date": os.environ['SEARCH_DATE'],
                    "arrival": "",
                    "passengers": os.environ['PASSENGERS'],
                    "pets": "0",
                    "step": "1"
                }
                
                logging.info(f"Visiting step 1 page with params: {params}")
                response = self.session.get(step1_url, params=params)
                logging.info(f"Step 1 page status: {response.status_code}")
                
                return True
            return False
            
        except Exception as e:
            logging.error(f"Error initializing session: {str(e)}")
            return False

    def check_availability(self):
        """Check cabin availability"""
        try:
            # Now make the actual availability check
            url = "https://www.minoan.gr/booking-api/trips"
            
            params = {
                "from": "PIR",
                "to": "HER",
                "date": os.environ['SEARCH_DATE'],
                "arrival": "",
                "passengers": os.environ['PASSENGERS'],
                "pets": "0",
                "step": "2",
                "vehicles": "0"
            }

            # Update referer for this specific request
            self.session.headers.update({
                'Referer': f"https://www.minoan.gr/booking?from=PIR&to=HER&date={params['date']}&arrival=&passengers={params['passengers']}&pets=0&step=1"
            })
            
            logging.info(f"Checking availability with params: {params}")
            response = self.session.get(url, params=params)
            
            logging.info(f"Availability check status: {response.status_code}")
            logging.info(f"Response headers: {dict(response.headers)}")
            logging.info(f"Response content preview: {response.text[:500]}")
            
            if response.status_code == 200:
                data = response.json()
                
                if data and len(data) > 0 and 'trips' in data[0]:
                    trip = data[0]['trips'][0]
                    
                    available_cabins = []
                    if 'accommodations' in trip and 'passenger' in trip['accommodations']:
                        for acc in trip['accommodations']['passenger']:
                            if acc['code'] in ['AB3', 'A3'] and acc['wholeBerthAvailability'] > 0:
                                available_cabins.append({
                                    'type': acc['name'],
                                    'availability': acc['wholeBerthAvailability'],
                                    'price': acc['price']
                                })
                    
                    if available_cabins:
                        self.send_notification(available_cabins, trip['departureDateTime'])
                        logging.info(f"Cabins found available for date: {params['date']}")
                        return True
                    
                    logging.info(f"No cabins available for date: {params['date']}")
                
            else:
                logging.error(f"Error response: {response.text}")
                
            return False

        except json.JSONDecodeError as e:
            logging.error(f"JSON Decode Error: {str(e)}")
            logging.error(f"Response content that caused error: {response.text}")
            return False
        except Exception as e:
            logging.error(f"Error checking availability: {str(e)}")
            return False

    def send_notification(self, available_cabins, departure_time):
        try:
            email_sender = os.environ['EMAIL_SENDER']
            email_password = os.environ['EMAIL_PASSWORD']
            email_recipient = os.environ['EMAIL_RECIPIENT']
            search_date = os.environ['SEARCH_DATE']
            passengers = os.environ['PASSENGERS']

            message = f"Cabins have become available for your desired date: {search_date}\n"
            message += f"Departure time: {departure_time}\n\n"
            message += "Available cabins:\n"
            
            for cabin in available_cabins:
                message += f"- {cabin['type']}\n"
                message += f"  Price: €{cabin['price']}\n"
                message += f"  Available berths: {cabin['availability']}\n\n"
            
            message += f"\nBook now at: https://www.minoan.gr/booking?from=PIR&to=HER&date={search_date}"
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
    
    session = MinoanSession()
    if session.init_session():
        session.check_availability()
    else:
        logging.error("Failed to initialize session")
