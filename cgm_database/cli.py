import sys
sys.path.insert(0, "..")
import warnings
warnings.filterwarnings("ignore")
import argparse
import os
import glob2 as glob
import time
import datetime
from cgmcore import utils
import numpy as np
import progressbar
import cv2
import pprint
import pickle
import dbutils
import pandas as pd


MEASUREMENTS_TABLE = "measurements"
IMAGES_TABLE = "image_data"
POINTCLOUDS_TABLE = "pointcloud_data"

commands = [
    "init",
    "updatemeasurements", # Uploads the CSV to the database.
    "updatemedia", 
    "statistics"
    # TODO "filterpcds", 
    # TODO "filterjpgs", 
    # TODO "sortpcds",
    # TODO "sortjpgs",
    # TODO "rejectqrcode",
    # TODO "acceptqrcode",
    # TODO "listrejected",
    # TODO "preprocess"
]

main_connector = dbutils.connect_to_main_database()

whhdata_path = "/whhdata"
media_subpath = "person"

def main():
    parse_args()
    execute_command()
    
    
# Parsing command-line arguments.

def parse_args():
    # Parse arguments from command-line.
    global args
    parser = argparse.ArgumentParser(description="Interact with the dataset database.")
    parser.add_argument("command", metavar='command', type=str, help="command to perform", nargs='+')
    parser.add_argument('--path', help="The folder of alignments",
        action=FullPaths, type=is_dir, default=whhdata_path)
    args = parser.parse_args()
    

class FullPaths(argparse.Action):
    """Expand user- and relative-paths"""
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))

def is_dir(dirname):
    """Checks if a path is an actual directory"""
    if not os.path.isdir(dirname):
        msg = "{0} is not a directory".format(dirname)
        raise argparse.ArgumentTypeError(msg)
    else:
        return dirname
    
    
# Executing commands.

def execute_command():
    result = None
    
    first_command = args.command[0]
    
    if first_command not in commands:
        print("ERROR: Invalid command {}! Valid commands are {}.".format(first_command, commands))
        # TODO print list of commands
    elif first_command == "init":
        result = execute_command_init()
    elif first_command == "updatemeasurements":
        result = execute_command_updatemeasurements()
    elif first_command == "updatemedia":
        result = execute_command_updatemedia()
    elif first_command == "statistics":
        result = execute_command_statistics()
    #elif first_command == "filterpcds":
    #    result = execute_command_filterpcds()
    #elif first_command == "filterjpgs":
    #    result = execute_command_filterjpgs()
    #elif first_command == "sortpcds":
    #    result = execute_command_sortpcds(sort_key="number_of_points", reverse=True)
    #elif first_command == "sortjpgs":
    #    result = execute_command_sortjpgs()
    #elif first_command == "rejectqrcode":
    #    assert len(args.command) == 2
    #    result = execute_command_rejectqrcode(args.command[1])
    #elif first_command == "acceptqrcode":
    #    assert len(args.command) == 2
    #    result = execute_command_acceptqrcode(args.command[1])
    #elif first_command == "listrejected":
    #    result = execute_command_listrejected()
    #elif first_command == "preprocess":
    #    result = execute_command_preprocess()
    else:
        raise Exception("Unexpected {}.".format(args.command))
        
    # Plot the result if there is one.
    if result != None:
        if type(result) == dict:
            #pp = pprint.PrettyPrinter(indent=4)
            pprint.pprint(result)
        else:
            print(result)
     
    
def execute_command_init():
    print("Initializing DB...")
    main_connector.execute_script_file("schema.sql")
    print("Done.")

    
def execute_command_updatemeasurements():
    print("Updating measurements...")
    
    # Where to get the data.
    glob_search_path = os.path.join(args.path, "*.csv")
    csv_paths = sorted(glob.glob(glob_search_path))
    csv_paths.sort(key=os.path.getmtime)
    csv_path = csv_paths[-1]
    print("Using {}".format(csv_path))

    # Load the data-frame.
    df = pd.read_csv(csv_path)
    
    # List all columns.
    columns = list(df)
    columns_mapping = { column: column for column in columns}
    columns_mapping["id"] = "measurement_id"
    columns_mapping["personId"] = "person_id"
    columns_mapping["age"] = "age_days"
    columns_mapping["height"] = "height_cms"
    columns_mapping["weight"] = "weight_kgs"
    columns_mapping["muac"] = "muac_cms"
    columns_mapping["headCircumference"] = "head_circumference_cms"
    columns_mapping["deletedBy"] = "deleted_by"
    columns_mapping["createdBy"] = "created_by"
    columns_mapping["personId"] = "person_id"
    
    table = MEASUREMENTS_TABLE

    # Number of rows before.
    rows_number = main_connector.get_number_of_rows(table)
    print("Number of rows before: {}".format(rows_number))

    # Drop table. # TODO consider update.
    #main_connector.clear_table(table)

    # Number of rows after.
    #rows_number = main_connector.get_number_of_rows(table)
    #print("Number of rows after clear: {}".format(rows_number))

    # Insert data in batches.
    batch_size = 1000
    sql_statement = ""
    rows_number_df = len(df.index)
    bar = progressbar.ProgressBar(max_value=rows_number_df)
    for index, row in df.iterrows():
        bar.update(index)

        keys = []
        values = []
        for df_key, db_key in columns_mapping.items():
            keys.append(str(db_key))
            values.append(str(row[df_key]))
        
        sql_statement += dbutils.create_insert_statement(table, keys, values)

        if index != 0 and ((index % batch_size) == 0 or index == rows_number_df - 1):
            main_connector.execute(sql_statement)
            sql_statement = ""

    bar.finish()

    # Number of rows after sync.
    rows_number = main_connector.get_number_of_rows(table)
    print("Number of rows after: {}".format(rows_number))
 

def execute_command_updatemedia(update_default_values=False):
    print("Updating media...")
    
    # Process JPGs.
    # TODO openpose
    # TODO ...
    table = IMAGES_TABLE
    glob_search_path = os.path.join(args.path, media_subpath, "**/*.jpg")
    print("Searching at {}... This might take a while!".format(glob_search_path))
    jpg_paths = glob.glob(glob_search_path) # TODO make this work again!
    #jpg_paths = ["/whhdata/person/MH_WHH_0153/measurements/1537860868501/rgb/rgb_MH_WHH_0153_1537860868501_104_95405.92970875901.jpg"]
    #jpg_paths = jpg_paths * 10000
    #print(len(jpg_paths))
    print("Found {} JPGs.".format(len(jpg_paths)))
    update_media_table(jpg_paths, IMAGES_TABLE, get_image_values)
    
    # Process PCDs.
    table = POINTCLOUDS_TABLE
    glob_search_path = os.path.join(args.path, media_subpath, "**/*.pcd")
    print("Searching at {}... This might take a while!".format(glob_search_path))
    pcd_paths = glob.glob(glob_search_path)
    #pcd_paths = ["/whhdata/person/MH_WHH_0030/measurements/1536913928288/pc/pc_MH_WHH_0030_1536913928288_104_000.pcd"]
    print("Found {} PCDs.".format(len(pcd_paths)))
    update_media_table(pcd_paths, POINTCLOUDS_TABLE, get_pointcloud_values)

    
def update_media_table(file_paths, table, get_values):
    insert_count = 0
    no_measurements_count = 0
    skip_count = 0
    bar = progressbar.ProgressBar(max_value=len(file_paths))
    sql_statement = ""
    batch_size = 1000
    last_index = len(file_paths) - 1
    for index, file_path in enumerate(file_paths):
        bar.update(index)
        
        # Check if there is already an entry.
        path = os.path.basename(file_path)
        sql_statement_select = dbutils.create_select_statement(table, ["path"], [file_path])
        results = main_connector.execute(sql_statement_select, fetch_all=True)
  
        # No results found. Insert.
        if len(results) == 0:
            insert_data = { "path": path }
            default_values = get_default_values(file_path, table)
            if default_values != None:
                insert_data.update(default_values)
                insert_data.update(get_values(file_path))
                sql_statement += dbutils.create_insert_statement(table, insert_data.keys(), insert_data.values())
                insert_count += 1
            else:
                no_measurements_count += 1
        
        # Found a result. Update.
        elif len(results) != 0:
            skip_count += 1
        
        # Update database.
        if index != 0 and ((index % batch_size) == 0) or index == last_index:
            if sql_statement != "":
                result = main_connector.execute(sql_statement)
                sql_statement = ""
   
    bar.finish()
    print("Inserted {} new entries.".format(insert_count))
    print("No measurements for {} entries.".format(no_measurements_count))
    print("Skipped {} entries.".format(skip_count))
    
    
def get_default_values(path, table):
    
    # Split and check the path.
    path_split = path.split("/")
    assert path_split[1] == whhdata_path[1:]
    assert path_split[2] == media_subpath
    
    # Get important values from path.
    qrcode = path_split[3]
    timestamp = path_split[-1].split("_")[-3]
    
    # Get id of measurement.
    threshold = int(60 * 60 * 24 * 1000)
    sql_statement = dbutils.create_select_statement("measurements", ["qrcode"], [qrcode])
    sql_statement = ""
    sql_statement += "SELECT id"
    sql_statement += " FROM measurements WHERE"
    sql_statement += " qrcode = '{}'".format(qrcode)
    sql_statement += " AND type = 'manual'"
    sql_statement += " AND ABS(timestamp - {}) < {}".format(timestamp, threshold)
    sql_statement += ";"
    results = main_connector.execute(sql_statement, fetch_all=True)
    
    # Measurement id not found. Return empty dictionary.
    if len(results) == 0:
        print("No measurement_id found for {}".format(path))
        return None

    # Found a measurement id.
    measurement_id = results[0][0]
    
    # Getting timestamp.
    last_updated, _ = get_last_updated()

    # Done.
    values = {}
    values["path"] = path
    values["qrcode"] = qrcode
    values["last_updated"] = last_updated
    values["rejected_by_expert"] = False
    values["measurement_id"] = measurement_id
    return values
    
    
def get_last_updated():
    last_updated = time.time()
    last_updated_readable = datetime.datetime.fromtimestamp(last_updated).strftime('%Y-%m-%d %H:%M:%S')
    return last_updated, last_updated_readable
    
    
def get_pointcloud_values(path):
    number_of_points = 0.0
    confidence_min = 0.0
    confidence_avg = 0.0
    confidence_std = 0.0
    confidence_max = 0.0
    error = False
    error_message = ""
    
    try:
        pointcloud = utils.load_pcd_as_ndarray(path)
        number_of_points = len(pointcloud)
        confidence_min = float(np.min(pointcloud[:,3]))
        confidence_avg = float(np.mean(pointcloud[:,3]))
        confidence_std = float(np.std(pointcloud[:,3]))
        confidence_max = float(np.max(pointcloud[:,3]))
    except Exception as e:
        print("\n", path, e)
        error = True
        error_message = str(e)
    except ValueError as e:
        print("\n", path, e)
        error = True
        error_message = str(e)
    
    values = {}
    values["number_of_points"] = number_of_points
    values["confidence_min"] = confidence_min
    values["confidence_avg"] = confidence_avg
    values["confidence_std"] = confidence_std
    values["confidence_max"] = confidence_max
    values["had_error"] = error
    values["error_message"] = error_message
    return values


def get_image_values(path):
    width = 0.0
    height = 0.0
    blur_variance = 0.0
    error = False
    error_message = ""
    try:
        image = cv2.imread(path)
        width = image.shape[0]
        height = image.shape[1]
        blur_variance = get_blur_variance(image)
    except Exception as e:
        print("\n", path, e)
        error = True
        error_message = str(e)
    except ValueError as e:
        print("\n", path, e)
        error = True
        error_message = str(e)

    values = {}
    values["width_px"] = width
    values["height_px"] = height
    values["blur_variance"] = blur_variance
    values["had_error"] = error
    values["error_message"] = error_message
    return values
    
    
def get_blur_variance(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(image, cv2.CV_64F).var()
 
 
def execute_command_statistics():
    result_string = ""
    
    tables = ["measurements", "image_data", "pointcloud_data"]
    for table in tables:
        sql_statement = "SELECT COUNT(*) FROM {};".format(table)
        result = main_connector.execute(sql_statement, fetch_one=True)
        result_string += "Table {} has {} entries.\n".format(table, result[0])
    
    return result_string
    
    
def execute_command_filterpcds(
    number_of_points_threshold=10000, 
    confidence_avg_threshold=0.75, 
    remove_errors=True, 
    remove_rejects=True, 
    sort_key=None, 
    sort_reverse=False):
    
    print("Filtering DB...")
    
    entries = db_connector.select_all(from_table="pcd_table")
    result_entries = []
    for values in entries:
        
        # Remove everything that does not have enough points.
        if int(values["number_of_points"]) < number_of_points_threshold:
            continue
        # Remove everything that does not have a high enough average confidence.
        if float(values["confidence_avg"]) < confidence_avg_threshold:
            continue
        # Remove everything that has an error.
        if remove_errors == True and bool(values["error"]) == True:
            continue
        # Remove everything that has been rejected by an expert.
        if remove_rejects == True and bool(values["rejected_by_expert"]) == True:
            continue
        result_entries.append(values)
        
    if sort_key != None:
        print("Sorting", sort_key, sort_reverse)
        result_entries = list(sorted(result_entries, key=lambda x: float(x[sort_key]), reverse=sort_reverse))   
    
    return { "results" : result_entries }

        
def execute_command_filterjpgs(
    blur_variance_threshold=100.0,
    remove_errors=True, 
    remove_rejects=True, 
    sort_key=None, 
    sort_reverse=False):
    
    print("Filtering DB...")
    
    entries = db_connector.select_all(from_table="jpg_table")
    result_entries = []
    for values in entries:
        
        # Remove that is too blurry.
        if int(values["blur_variance"]) < blur_variance_threshold:
            continue
        # Remove everything that has an error.
        if remove_errors == True and bool(values["error"]) == True:
            continue
        # Remove everything that has been rejected by an expert.
        if remove_rejects == True and bool(values["rejected_by_expert"]) == True:
            continue
        result_entries.append(values)
        
    if sort_key != None:
        print("Sorting", sort_key, sort_reverse)
        result_entries = list(sorted(result_entries, key=lambda x: float(x[sort_key]), reverse=sort_reverse))   
    
    return { "results" : result_entries }
        
        
def execute_command_sortpcds(sort_key, sort_reverse):
    print("Sorting DB...")
    
    entries = db_connector.select_all(from_table="pcd_table")
    sorted_entries = sorted(entries, key=lambda x: x[sort_key], reverse=sort_reverse)
    
    return { "results" : sorted_entries }
    
        
def execute_command_sortjpgs(sort_key, reverse):
    assert False, "Implement!"


def execute_command_rejectqrcode(qrcode):
    print("Rejecting QR-code...")
    
    # Reject PCDs.
    entries = db_connector.select_all(from_table="pcd_table", where=("qrcode", qrcode))
    for entry in entries:
        if entry["rejected_by_expert"] == True:
            print("{} already rejected. Skipped.".format(entry["id"]))
            continue
        entry["rejected_by_expert"] = True
        last_updated, last_updated_readable = get_last_updated()
        entry["last_updated"] = last_updated
        entry["last_updated_readable"] = last_updated_readable
        db_connector.insert(into_table="pcd_table", id=entry["id"], values=entry)
        print("{} rejected.".format(entry["id"]))
    db_connector.synchronize()

    # Reject JPGs.
    entries = db_connector.select_all(from_table="jpg_table", where=("qrcode", qrcode))
    for entry in entries:
        if entry["rejected_by_expert"] == True:
            print("{} already rejected. Skipped.".format(entry["id"]))
            continue
        entry["rejected_by_expert"] = True
        last_updated, last_updated_readable = get_last_updated()
        entry["last_updated"] = last_updated
        entry["last_updated_readable"] = last_updated_readable
        db_connector.insert(into_table="jpg_table", id=entry["id"], values=entry)
        print("{} rejected.".format(entry["id"]))
    db_connector.synchronize()

    
def execute_command_acceptqrcode(qrcode):
    print("Rejecting QR-code...")
    
    # Accept PCDs.
    entries = db_connector.select_all(from_table="pcd_table", where=("qrcode", qrcode))
    for entry in entries:
        if entry["rejected_by_expert"] == False:
            print("{} already accepted. Skipped.".format(entry["id"]))
            continue
        entry["rejected_by_expert"] = False
        last_updated, last_updated_readable = get_last_updated()
        entry["last_updated"] = last_updated
        entry["last_updated_readable"] = last_updated_readable
        db_connector.insert(into_table="pcd_table", id=entry["id"], values=entry)
        print("{} accepted.".format(entry["id"]))
    db_connector.synchronize()

    # Accept JPGs.
    entries = db_connector.select_all(from_table="jpg_table", where=("qrcode", qrcode))
    for entry in entries:
        if entry["rejected_by_expert"] == False:
            print("{} already accepted. Skipped.".format(entry["id"]))
            continue
        entry["rejected_by_expert"] = False
        last_updated, last_updated_readable = get_last_updated()
        entry["last_updated"] = last_updated
        entry["last_updated_readable"] = last_updated_readable
        db_connector.insert(into_table="jpg_table", id=entry["id"], values=entry)
        print("{} accepted.".format(entry["id"]))
    db_connector.synchronize()
 

def execute_command_listrejected():
    
    return {
        "rejected_pcds": db_connector.select_all(from_table="pcd_table", where=("rejected_by_expert", True)),
        "rejected_jpgs": db_connector.select_all(from_table="jpg_table", where=("rejected_by_expert", True))
    }
    

def execute_command_preprocess(preprocess_pcds=True, preprocess_jpgs=False):
    print("Preprocessing data-set...")
    
    # Create the base-folder.
    datetime_path = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
    base_path = os.path.join(preprocessed_root_path, datetime_path)
    os.mkdir(base_path)
    os.mkdir(os.path.join(base_path, "pcd"))
    os.mkdir(os.path.join(base_path, "jpg"))
    
    # Process the filtered PCDs.
    if preprocess_pcds == True:
        entries = execute_command_filterpcds()["results"]
        print("Found {} PCDs. Processing...".format(len(entries)))
        bar = progressbar.ProgressBar(max_value=len(entries))
        for index, entry in enumerate(entries):
            bar.update(index)
            path = entry["path"]
            if os.path.exists(path) == False:
                print("\n", "File {} does not exist!".format(path), "\n")
                continue
            pointcloud = utils.load_pcd_as_ndarray(path)
            targets = np.array([float(value) for value in entry["targets"].split(",")])
            qrcode = entry["qrcode"]
            pickle_filename = entry["id"].replace(".pcd", ".p")
            qrcode_path = os.path.join(base_path, "pcd", qrcode)
            if os.path.exists(qrcode_path) == False:
                os.mkdir(qrcode_path)
            pickle_output_path = os.path.join(qrcode_path, pickle_filename)
            pickle.dump((pointcloud, targets), open(pickle_output_path, "wb"))
        bar.finish()
    
    # Process the filtered JPGs.
    if preprocess_jpgs == True:
        entries = execute_command_filterjpgs()["results"]
        print("Found {} JPGs. Processing...".format(len(entries)))
        bar = progressbar.ProgressBar(max_value=len(entries))
        for index, entry in enumerate(entries):
            bar.update(index)
            path = entry["path"]
            if os.path.exists(path) == False:
                print("\n", "File {} does not exist!".format(path), "\n")
                continue
            image = cv2.imread(path)
            targets = np.array([float(value) for value in entry["targets"].split(",")])
            qrcode = entry["qrcode"]
            pickle_filename = entry["id"].replace(".jpg", ".p")
            qrcode_path = os.path.join(base_path, "jpg", qrcode)
            if os.path.exists(qrcode_path) == False:
                os.mkdir(qrcode_path)
            pickle_output_path = os.path.join(qrcode_path, pickle_filename)
            pickle.dump((image, targets), open(pickle_output_path, "wb"))
        bar.finish()
    
        
if __name__ == "__main__":
    main()