# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the application files to the container
COPY . /app/

# Install any needed packages
RUN pip install --no-cache-dir -r requirements.txt

# Expose a port if needed (not strictly required for this app)
#EXPOSE 8080

# Run the application
CMD ["python", "main.py"]
