#!/bin/bash

socket_addr=127.0.0.1:5000
app_name="masterplotter"
log_dir=./logs
gunicorn_error_log="$log_dir/gunicorn-error.log"
gunicorn_access_log="$log_dir/gunicorn-access.log"

# -d INPUT_DIRECTORY, used to specify the directory of the experiments on which to run the statsMaster.py file
# Note: colon in front of 'd' after getopts is to put getopts into silent mode which is the recommended
# while the colon after the 'd' is to signal that the option takes an argument
while getopts ":d:" opt; do
    case "$opt" in
        d)
            log_path="$log_dir/error.log"
            work_dir=./work
            db_path=./db.sqlite
            db_table_name=master

            printf "Running stats master on supplied directory\n"
            temp_csv_file=./"$db_table_name".csv
            printf "Starting to build master file...\n"
            if ! python3 ../../PyMimircache/driver/statsMaster.py -i $OPTARG -o "$temp_csv_file"; then
                printf "Error occurred while trying to build master file!\n"
                exit 1
            fi
            printf "done building master file.\n"
            
            printf "Importing data into database...\n"
            if ! python3 ./sqlite-import-csv.py -i "$temp_csv_file" -o "$db_path" -x workload devices algorithms "write policy"; then
                printf "Error occurred while trying to import data into database!\n"
                exit 1
            fi
            # remove temporary CSV file
            rm "$temp_csv_file"

            # setup file and directory structure
            mkdir "$work_dir" "$log_dir"
            touch "$log_path" "$gunicorn_error_log" "$gunicorn_access_log"
            # create configuration file for application
            config_file=./config.json
            printf '{"LOG_PATH":"%s","WORK_DIR":"%s","DB_PATH":"%s","DB_TABLE_NAME":"%s"}' \
                     "$log_path" "$work_dir" "$db_path" "$db_table_name" > "$config_file"
            ;;
        \?)
            # the >&2 is meant to redirect the printf to print to stderr instead of stdout (i.e. 1)
            >&2 printf "Invalid option: -%s\n" "$OPTARG"
            exit 1
            ;;
        \:)
            >&2 printf "Required argument not found: -%s\n" "$OPTARG"
            exit 1
            ;;
    esac
done

# run app in background
printf "Starting gunicorn server in the background with name: %s, at address: %s.\n" "$app_name" "$socket_addr"
gunicorn --bind "$socket_addr"                     \
         --error-logfile "$gunicorn_error_log"     \
         --access-logfile "$gunicorn_access_log"   \
         --name "$app_name"                        \
         --daemon master-plotter:app
         