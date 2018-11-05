# Autobot: A Telegram bot for car allocation
## Local testing instructions
The following instructions are for Linux machines, they must be modified accordingly for Windows and Mac.
### Preparation
1. Prerequisites: you need a local install of Python 3, together with the pip package manager and virtualenv;
1. Install the [Google Cloud SDK](https://cloud.google.com/sdk/) outside of the project directory (if you chose to not add the `gcloud` executable in the PATH, substitute it in the rest of the documentation with `<PATH_TO_GCLOUD_SDK>/bin/gcloud`);
1. Install the Python App Engine extensions: `gcloud components install app-engine-python`
1. Install the [Datastore emulator](https://cloud.google.com/datastore/docs/tools/datastore-emulator): `gcloud components install cloud-datastore-emulator`
1. From the shell, while inside the project directory, create a new Python virtual environment: `virtualenv --python python3 env`. The following commands must be executed from the same shell without changing location.
1. Activate the new environment: `source env/bin/activate`
1. Install the runtime dependencies: `pip install -r requirements.txt`

### Starting of a local testing session
1. Run the datastore emulator: `gcloud beta emulators datastore start --no-store-on-disk --project dei-projects` (omit the `--no-store-on-disk` part if you want the datastore content to persist across the emulator restarts)
1. In another shell, initialize the needed environment variables: `$(gcloud beta emulators datastore env-init)`. The following commands must be executed inside the shell where this command has been executed.
1. Activate the Python virtual environment: `source env/bin/activate`
1. If new dependencies are needed, install them: `pip install -r requirements.txt`
1. Run the application: `python main.py`

The code executed while in debugging mode is inside the `if __name__ == '__main__':` block. Remember that no connection to Telegram is possible while running locally (actually, that is possible, but you have to change a portion of the code and register a testing bot in Telegram), therefore, you cannot call command handlers directly. An exception is valid for simple handlers, where the mock `update` object is able to mimick the necessary functionality of Telegram. In this case, the answer will be printed to screen, instead of being sent to Telegram servers.

## Deployment
### Preparation
1. Perform the preparation steps for local testing
1. In the project folder, activate the Python virtual environment: `source env/bin/activate`
1. Install a local copy of the runtime dependencies: `pip install -t lib -r requirements.txt`

### Deploy a new version of the app
1. If new dependencies have been added from the last deployment, install them from inside the project folder: `pip install -t lib -r requirements.txt`
1. Deploy the app: `gcloud app deploy`
