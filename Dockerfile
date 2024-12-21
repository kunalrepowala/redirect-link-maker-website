# Use the official Python image from Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . .

# Expose port 8080
EXPOSE 8080

# Set the environment variable for Flask to run on port 8080
ENV FLASK_RUN_PORT=8080

# Run the application
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
