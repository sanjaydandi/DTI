import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set environment variable to prevent database reset
os.environ['PRESERVE_DB'] = 'True'

from app import app

if __name__ == "__main__":
    app.run(debug=True)