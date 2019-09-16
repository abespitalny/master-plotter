# master-plotter
An interactive plotting tool built on Plotly.js

## Dependencies
The web app component runs on Python 3 with the following dependencies:
* Flask
* pandas
* gunicorn

These can be installed by running `pip3 install -r requirements.txt`
or if using the Anaconda environment `conda install --file requirements.txt`.

## Running master-plotter
To get started with master-plotter, if you are running it for the first time
without the database and configurations being set up already then
run `./run-plotter.sh -d <DIR>` where `DIR` points to the root directory of experiments.
This will conveniently bundle the experiments and insert them into an SQLite database
and set up the directory structure and configuration file that master-plotter requires.
On subsequent runs, you can simply run `./run-plotter.sh` without supplying the experiment directory.