FROM node:20-alpine

WORKDIR /app

# Copy only package.json first to leverage Docker cache
COPY package.json ./

# Install dependencies using yarn (will just generate a local lockfile)
RUN yarn install

COPY . .

ARG REACT_APP_BACKEND_URL
ENV REACT_APP_BACKEND_URL=$REACT_APP_BACKEND_URL

# Build the react application
RUN yarn build

# Install serve globally
RUN yarn global add serve

EXPOSE 3000

# Start the frontend
CMD ["serve", "-s", "build", "-l", "3000"]
