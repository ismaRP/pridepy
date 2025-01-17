#!/usr/bin/env python

import glob
import logging
import os
import re
import shutil
import urllib
import urllib.request

from util.api_handling import Util


class Files:
    """
    This class handles PRIDE API files endpoint.
    """

    api_base_url = "https://www.ebi.ac.uk/pride/ws/archive/v2/"

    def __init__(self):
        pass

    def get_all_paged_files(self, query_filter, page_size, page, sort_direction, sort_conditions):
        """
         Get all filtered pride submission files
        :param query_filter: Parameters to filter the search results
        :param page_size: Number of results to fetch in a page
        :param page: Identifies which page of results to fetch
        :param sort_direction: Sorting direction: ASC or DESC
        :param sort_conditions: Field(s) for sorting the results on
        :return: paged file list on JSON format
        """
        """
           
        """
        request_url = self.api_base_url + "files?"

        if query_filter:
            request_url = request_url + "filter=" + query_filter + "&"

        request_url = request_url + "pageSize=" + str(page_size) + "&page=" + str(page) + "&sortDirection=" + sort_direction + "&sortConditions=" + sort_conditions

        headers = {"Accept": "application/JSON"}
        response = Util.get_api_call(request_url, headers)
        return response.json()

    def get_all_raw_file_list(self, project_accession):
        """
        Get all raw file list from PRIDE API for a given project_accession
        :param project_accession: PRIDE accession
        :return: raw file list in JSON format
        """

        request_url = self.api_base_url + "files/byProject?accession=" + project_accession + ",fileCategory.value==RAW"
        headers = {"Accept": "application/JSON"}

        response = Util.get_api_call(request_url, headers)
        return response.json()

    def download_raw_files_from_ftp(self, accession, output_folder):
        """
        This method will download all the raw files from PRIDE FTP
        :param output_folder: output directory where raw files will get saved
        :param accession: PRIDE accession
        :return: None
        """

        if not (os.path.isdir(output_folder)):
            os.mkdir(output_folder)

        response_body = self.get_all_raw_file_list(accession)

        self.download_files_from_ftp(response_body, output_folder)

    @staticmethod
    def download_files_from_ftp(file_list_json, output_folder):
        """
        Download files using ftp transfer url
        :param file_list_json: file list in json format
        :param output_folder: folder to download the files
        """
        for file in file_list_json:
            if file['publicFileLocations'][0]['name'] == 'FTP Protocol':
                ftp_filepath = file['publicFileLocations'][0]['value']
            else:
                ftp_filepath = file['publicFileLocations'][1]['value']
            logging.debug('ftp_filepath:' + ftp_filepath)
            public_filepath_part = ftp_filepath.rsplit('/', 1)
            logging.debug(file['accession'] + " -> " + public_filepath_part[1])
            new_file_path = public_filepath_part[1]
            urllib.request.urlretrieve(ftp_filepath, output_folder + new_file_path)

    def get_submitted_file_path_prefix(self, accession):
        """
        At pride repository, public data is disseminated according to a proper structure.
        I.e. base/path/ + yyyy/mm/accession/ + submitted/
        This extracts the yyyy/mm/accession path fragment from the API by examine the file path
        of a public file.
        I.e. ftp://ftp.pride.ebi.ac.uk/pride/data/archive/2018/10/PXD008644/7550GI_Y.raw
        :param accession: PRIDE accession
        :return: path fragment (eg: 2018/10/PXD008644)
        """
        results = self.get_all_raw_file_list(accession)
        first_file = results[0]['publicFileLocations'][0]['value']
        path_fragment = re.search(r'\d{4}/\d{2}/PXD\d*', first_file).group()
        return path_fragment

    @staticmethod
    def get_files_from_dir(location, regex):
        """
        match files with provided regex in the source location
        :param regex: files to match
        :param location: location to search files
        :return:
        """

        file_list_from_dir = []

        for file in glob.glob(location + regex):
            logging.debug("found file: " + file)
            filename = file.rsplit('/', 1)[1]
            file_list_from_dir.append(filename)
        return file_list_from_dir

    def copy_raw_files_from_dir(self, accession, source_base_directory):
        """
        This function copy raw files from the given directory if they are in the PRIDE FTP folder.
        When copying, prefix the file accession given by PRIDE archive
        :param accession: pride project accession
        :param source_base_directory : file path of the given directory
        """

        # get the full path where you can find the raw files in the file system
        # to support that, data should be written in following format:
        # base/path/ + yyyy/mm/accession/ + submitted/
        path_fragment = self.get_submitted_file_path_prefix(accession)
        complete_source_dir = source_base_directory + "/" + path_fragment + "/submitted/"

        if not (os.path.isdir(complete_source_dir)):
            logging.exception("Folder does not exists! " + complete_source_dir)

        # get the list of raw files from the given directory
        file_list_from_dir = self.get_files_from_dir(complete_source_dir, "*.raw")

        response_body = self.get_all_raw_file_list(accession)

        self.copy_from_dir(complete_source_dir, file_list_from_dir, response_body)

    def download_file_from_ftp_by_name(self, accession, file_name, output_folder):
        """
        Download files from ftp url
        :param accession: PRIDE accession
        :param file_name: file name to download
        :param output_folder: folder to download the files
        """

        if not (os.path.isdir(output_folder)):
            os.mkdir(output_folder)
        response = self.get_file_from_api(accession, file_name)
        self.download_files_from_ftp(response, output_folder)

    def copy_file_from_dir_by_name(self, accession, file_name, input_folder):
        path_fragment = self.get_submitted_file_path_prefix(accession)
        complete_source_dir = input_folder + "/" + path_fragment + "/submitted/"

        if not (os.path.isdir(complete_source_dir)):
            logging.exception("Folder does not exists! " + complete_source_dir)

        file_list_from_dir = self.get_files_from_dir(complete_source_dir, file_name)
        response_body = self.get_file_from_api(accession, file_name)

        self.copy_from_dir(complete_source_dir, file_list_from_dir, response_body)

    def get_file_from_api(self, accession, file_name):
        """
        Fetches file from API
        :param accession: PRIDE accession
        :param file_name: file name
        :return: file in json format
        """
        request_url = self.api_base_url + "files/byProject?accession=" + accession + ",fileName==" + file_name
        headers = {"Accept": "application/JSON"}
        try:
            response = Util.get_api_call(request_url, headers)
            return response.json()
        except Exception as e:
            raise Exception("File not found" + str(e))

    @staticmethod
    def copy_from_dir(complete_source_dir, file_list_from_dir, file_list_json):
        """
        Copy files from nfs directory
        :param complete_source_dir: nfs directory
        :param file_list_from_dir: files to copy
        :param file_list_json: file list from api
        :return:
        """
        for file in file_list_json:
            ftp_filepath = file['publicFileLocations'][0]['value']
            file_name_from_ftp = ftp_filepath.rsplit('/', 1)[1]
            if file_name_from_ftp in file_list_from_dir:
                source_file = complete_source_dir + file_name_from_ftp
                destination_file = file['accession'] + "-" + file_name_from_ftp
                shutil.copy2(source_file, destination_file)
            else:
                logging.error(file_name_from_ftp + " not found in " + complete_source_dir)
