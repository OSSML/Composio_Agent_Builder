# Use Node.js as the base image
FROM node:20-slim

# Set the working directory for the frontend application
WORKDIR /frontend

# Copy the package.json and package-lock.json first (to leverage caching)
COPY package.json package-lock.json /frontend/

# Install dependencies
RUN npm install

# Copy the rest of the frontend code
COPY . /frontend/

# Expose the port for the React app (default 3000)
EXPOSE 3000

# Command to start the React app
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--no-open"]
