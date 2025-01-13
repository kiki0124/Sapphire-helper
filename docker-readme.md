# Discord Bot Setup with Docker
This project contains a Discord bot containerized with Docker. You can easily run it using `docker run` (instructions below).

## Installing Docker Desktop

1. **Download and install Docker Desktop** from [Docker's official website](https://www.docker.com/products/docker-desktop).
2. Start Docker Desktop once installed.

## Running the Bot
Cd into the root directory (the directory where we have the Dockerfile) and run the following command:

```bash
   docker build -t sapphire-helper . && docker run --env-file .env -v ./database:/app/database sapphire-helper
```

### Explanation:
- `docker build`: This command tells Docker to build a Docker image.
- `-t sapphire-helper`: The -t flag assigns a tag (name) to the image you're building. In this case, the image will be named sapphire-helper.
- `.`: This represents the current directory as the build context. Docker will look for the Dockerfile in the current directory to build the image.
- `&&`: The && is a logical AND operator, which means the second command (docker run) will only run if the first command (docker build) succeeds.
- `docker run`: This command tells Docker to run a container based on the sapphire-helper image that was just built.
- `--env-file .env`: Loads environment variables from the .env file located in the current directory (.). 
- `-v`: -v is used to mount a volume between the host and the container. . 
- `./database`: The database directory on your host machine (relative to where you are running the Docker command). 
- `/app/database`: The directory inside the container where the host directory (./database) will be mounted. This makes the ./database directory from the host machine accessible inside the container at /app/database
This is useful for persistent storage (e.g., for databases or files) because changes made to files inside /app/database will also appear in ./database on the host.
- `sapphire-helper`: This is the name of the Docker image you built earlier. Docker will create and run a container from this image.

### Changes made to the codebase
1. Added `Dockerfile` (this file contains the instruction for docker to build the docker image)
2. Created `/database` directory, the `data.db` will be inside this directory - Why? - because while using docker we need to store the database directly on the host system so that the database won't be deleted if we remove or stop the Container where the bot is running
3. Updated `functions.py` to use the new path for database, added a constant `DB_PATH` which will have the path to database
4. Added `.dockerfile` to ignore certain files from adding to docker image during build (similar to .gitignore)

### Note:
1. The docker command mentioned above will run the docker container in **interactive mode** so that we will get logs on our terminal directly, but for production (deploying on servers) we need the container to run on **detached mode** so add the `-d` flag to the docker command before running it, the command should look like this:

``` sh
   docker build -t sapphire-helper . && docker run -d --env-file .env -v ./database:/app/database sapphire-helper
```

2. Changing the codebase (like adding new features, or modifying existing feature) won't break the docker configuration most of the times so this docker setup works like set it and forgot it, but it is highly recomended to test running the docker locally before pushing the new changes to github (just to be safe)