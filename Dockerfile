# Use a lightweight Python base image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy dependency file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app code
COPY . .

# Expose the port Flask runs on (default is 5000)
EXPOSE 5000

# Command to run the app (using Gunicorn for production stability)
# Replace 'app:app' with 'your_filename:your_flask_variable'
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "flask_backend:app"]