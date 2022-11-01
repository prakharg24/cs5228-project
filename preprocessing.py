import copy

import numpy as np
import pandas as pd

from dataloader import remove_columns, convert_to_categorical, convert_to_continuous, convert_to_lowercase, convert_to_onehot, use_target_encoding
from dataloader import extract_unit_types, extract_floor_level, extract_tenure, fill_lat_lng_knn, replace_corrupted_lat_lng
from dataloader import append_auxiliary_data_subzone, append_auxiliary_data_infra

from sklearn.impute import KNNImputer


def reverse_dict(inp_dict):
    return {v:k for k, v in inp_dict.items()}

def drop_outliers(trainX, trainY):
    index_list_to_remove = []
    index_list_to_remove.extend(trainX.index[~(trainX['size_sqft'] > 300)].tolist())
    index_list_to_remove.extend(trainY.index[~((trainY > 0) & (trainY < 2 * 10 ** 8))].tolist())
    index_list_to_remove.extend([14218, 15027, 4347, 663, 19587, 13461])

    trainX.drop(index=index_list_to_remove, inplace=True)
    trainY.drop(index=index_list_to_remove, inplace=True)


def drop_unnecessary_columns(df):
    labels_to_remove = ['listing_id', 'title', 'property_details_url', 'elevation', 'available_unit_types']
    # TODO Suggestion : Can we extract some information from the title?
    # TODO Suggestion : Can we mine some information from the url? Probably not, since the URLs lead to 404 error in most cases
    # elevation is simply 0 for all entries
    # floor_level is NaN for more than 80% of the data
    # TODO Suggestion : Maybe we can still use the floor_level information of the rest 20% examples
    # address and property_name are also dropped for now
    df = remove_columns(df, col_labels=labels_to_remove)

    return df

def drop_remaining_columns(df):
    cols = [col for col in df.columns if "floor_level" in col]
    cols.extend(['address', 'property_name','tenure'])
    df = remove_columns(df, cols)
    return df

def round_off_columns(df):
    labels_to_round_off = ['built_year', 'num_beds', 'num_baths']
    for col in labels_to_round_off:
        df[col] = df[col].apply(np.ceil)

    return df


def preprocess_data_for_visualization(trainX, trainY, testX):
    trainX, testX = convert_to_lowercase(trainX), convert_to_lowercase(testX)
    trainX_orig, trainY_orig = copy.deepcopy(trainX), copy.deepcopy(trainY)
    drop_outliers(trainX_orig, trainY_orig)
    trainX_orig = drop_unnecessary_columns(trainX_orig)

    trainX_processed, trainY_processed, _ = preprocess_data_for_classification(trainX, trainY, testX)

    columns_to_copy = ['built_year', 'num_beds', 'num_baths', 'size_sqft']
    for col in columns_to_copy:
        trainX_orig[col] = trainX_processed[col]

    return trainX_orig, trainY_orig


def preprocess_data_for_classification(trainX, trainY, testX, auxSubzone=None, auxInfraDict={}):

    drop_outliers(trainX, trainY)

    # Convert all strings to lowercase for easy processing later
    trainX, testX = convert_to_lowercase(trainX), convert_to_lowercase(testX)

    # There are 10 values for the furnishing feature set as 'na' in the training set. Changing them to 'unspecified'.
    trainX['furnishing'] = trainX['furnishing'].replace('na', 'unspecified')
    testX['furnishing'] = testX['furnishing'].replace('na', 'unspecified')

    trainX["property_type"] = trainX["property_type"].replace(r'hdb.*', 'hdb', regex=True)
    testX["property_type"] = testX["property_type"].replace(r'hdb.*', 'hdb', regex=True)

    # All leasehold in 100 year range are equivalent to 99-year leasehold, and all leashold in 900_ range are quivalent to freehold
    # for leasehold in ['947-year leasehold', '929-year leasehold', '946-year leasehold', '956-year leasehold', '999-year leasehold']:
    #     trainX['tenure'] = trainX['tenure'].replace(leasehold, 'freehold')
    #     testX['tenure'] = testX['tenure'].replace(leasehold, 'freehold')
    # for leasehold in ['100-year leasehold', '102-year leasehold', '110-year leasehold', '103-year leasehold']:
    #     trainX['tenure'] = trainX['tenure'].replace(leasehold, '99-year leasehold')
    #     testX['tenure'] = testX['tenure'].replace(leasehold, '99-year leasehold')

    trainX, testX = drop_unnecessary_columns(trainX), drop_unnecessary_columns(testX)

    # Remove corrupted lat lng Values
    trainX, testX = replace_corrupted_lat_lng(trainX), replace_corrupted_lat_lng(testX)

    for ele in auxInfraDict:
        trainX = append_auxiliary_data_infra(trainX, ele, auxInfraDict[ele])
        testX = append_auxiliary_data_infra(testX, ele, auxInfraDict[ele])

    # Clean floor level values
    trainX, testX = extract_floor_level(trainX), extract_floor_level(testX)

    trainX, testX = extract_tenure(trainX), extract_tenure(testX)

    # labels_to_category = ['property_type', 'tenure', 'furnishing', 'subzone', 'planning_area']
    labels_to_category = ['property_type', 'subzone', 'planning_area', 'tenure', 'furnishing', 'floor_level', 'address', 'property_name']
    # TODO : property_type also contains information about types of available units, which needs to separately extracted
    trainX, category_to_int_dict = convert_to_categorical(trainX, col_labels=labels_to_category)
    testX, _ = convert_to_categorical(testX, col_labels=labels_to_category, category_to_int_dict=category_to_int_dict)

    # These categories do not contain any NaN values : address, property_name, property_type, furnishing, lat, lng, size_sqft
    # Handling NaN values : tenure - Let the NaNs be their own category

    # Handling NaN values : subzone and planning_area - Use k-nearest neighbors and lat/lng values to find their subzone and planning_area
    nan_index = category_to_int_dict['subzone'][np.nan]
    trainX, knngraph_subzone = fill_lat_lng_knn(trainX, 'subzone', nan_index)
    testX, _ = fill_lat_lng_knn(testX, 'subzone', nan_index, knngraph=knngraph_subzone)

    nan_index = category_to_int_dict['planning_area'][np.nan]
    trainX, knngraph_planning_area = fill_lat_lng_knn(trainX, 'planning_area', nan_index)
    testX, _ = fill_lat_lng_knn(testX, 'planning_area', nan_index, knngraph=knngraph_planning_area)

    if auxSubzone is not None:
        trainX = append_auxiliary_data_subzone(trainX, reverse_dict(category_to_int_dict['subzone']), auxSubzone)
        testX = append_auxiliary_data_subzone(testX, reverse_dict(category_to_int_dict['subzone']), auxSubzone)

    labels_to_onehot = ['furnishing', 'floor_level']
    trainX = convert_to_onehot(trainX, col_labels=labels_to_onehot, category_to_int_dict=category_to_int_dict)
    testX = convert_to_onehot(testX, col_labels=labels_to_onehot, category_to_int_dict=category_to_int_dict)

    knn_imputer = KNNImputer(n_neighbors=7, weights='distance')
    trainX = pd.DataFrame(knn_imputer.fit_transform(trainX), columns=trainX.columns)
    testX = pd.DataFrame(knn_imputer.transform(testX), columns=testX.columns)

    trainX, testX = round_off_columns(trainX), round_off_columns(testX)

    labels_to_target_encode = ['subzone', 'planning_area', 'property_type']
    trainX, category_to_target_dict = use_target_encoding(trainX, trainY, col_labels=labels_to_target_encode)
    testX, _ = use_target_encoding(testX, None, col_labels=labels_to_target_encode, category_to_int_dict=category_to_target_dict)

    # groups = trainX.groupby(['property_type', 'num_beds', 'num_baths', 'subzone']).indices
    # groups.update(trainX.groupby(['property_type', 'subzone']).indices)
    # groups.update(trainX.groupby(['property_type']).indices)
    # target_encoding = {
    #     group: np.mean(np.take(trainY, index_list)) for group, index_list in groups.items()
    # }
    #
    # def custom_map(row):
    #     key1 = (row['property_type'], row['num_beds'], row['num_baths'], row['subzone'])
    #     key2 = (row['property_type'], row['subzone'])
    #     if key1 in target_encoding:
    #         return target_encoding[key1]
    #     elif key2 in target_encoding:
    #         return target_encoding[key2]
    #     else:
    #         return target_encoding[row['property_type']]
    #
    # trainX['property_type'] = trainX.apply(lambda r: custom_map(r), axis=1)
    # testX['property_type'] = testX.apply(lambda r: custom_map(r), axis=1)

    # Done after filling subzone values

    # Handling NaN values : built_year - Just provide them with the average value
    # Handling NaN values : num_beds - Just provide them with the average value
    # Handling NaN values : num_baths - Just provide them with the average value
    # Handling NaN values : total_num_units - Just provide them with the average value

    # Handling available_unit_types
    # trainX, testX = extract_unit_types(trainX), extract_unit_types(testX)

    ## TODO : Temporary handling of missing entries and NaNs!! Needs to be revisited
    trainX, testX = drop_remaining_columns(trainX), drop_remaining_columns(testX)

    trainX = trainX.fillna(trainX.mean())
    testX = testX.fillna(trainX.mean())

    return trainX, trainY, testX
