#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#       styleneFolding.py
#
#       Kim Luyckx <kim.luyckx@ua.ac.be>
#       Frederik Vaassen <frederik.vaassen@ua.ac.be>
#       Copyright 2011-2012 CLiPS Research Center
#
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.
#

'''
Generate instances for cross-validation experiments using Stylene, the
JAVA-based instance generation package.

Prerequisites are:
- a recent, working version of Stylene (2012/03/04 or later)
- a folder with your folds in the appropriate structure (see styleneFolding.py -h)
- a startparameters file (in the same directory as this script) with the
configuration you wish to use for Stylene.

Make sure you adapt the path to Stylene below.

'''

__author__ = 	'Kim Luyckx (kim.luyckx@ua.ac.be); \
				Frederik Vaassen (frederik.vaassen@ua.ac.be)'

import sys
import os
import re
import subprocess
from distutils import dir_util, file_util
from xml.etree.ElementTree import ElementTree
from optparse import OptionParser

import logging
import logging.handlers

overwrite_instances = False

def getFolds(dataDIR):
	'''
	List the folders that need to be in each train or test partition.

	'''
	folds = sorted([os.path.join(dataDIR, folder) for folder in os.listdir(dataDIR) if re.match('fold-\d+', folder)])

	classes = set()
	num_classes = None
	for fold in folds:
		labels = os.listdir(fold)
		if num_classes == None:
			num_classes = len(labels)
		else:
			assert num_classes == len(labels), '{0} does not seem to have the same number of classes ({1}): {2}'.format(fold, num_classes, str(labels))
		for label in labels:
			classes.add(label)

	if len(folds) == 1:
		folds = [([folds[0]], None)]
	else:
		folds = [(folds[:i]+folds[i+1:], folds[i]) for i in range(len(folds))]

	realized_folds = []
	for (train, test) in folds:
		if test is not None:
			test_folders = [os.path.join(test, d) for d in os.listdir(test)]
		else:
			test_folders = None
		train_folders =[]
		for folder in train:
			train_folders.extend([os.path.join(folder, d) for d in os.listdir(folder)])
		realized_folds.append((train_folders, test_folders))

	return realized_folds, classes

def removeDSstore(dataDIR):
	'''
	Runs through a directory and all its subdirectories, and deletes all
	.DS_Store files.

	'''
	for root, dirs, files in os.walk(dataDIR):
		for f in files:
			if f == '.DS_Store':
				log.debug('Removing .DS_Store at {0}'.format(os.path.join(root, f)))
				os.remove(os.path.join(root, f))

def main(dataDIR, outputDIR):

	dataDIR = os.path.abspath(dataDIR)
	outputDIR = os.path.abspath(outputDIR)

	# Get rid of all those pesky DS_Store files.
	removeDSstore(dataDIR)
	# Get the files that will be contained in each fold and list the labels used.
	folds, classes = getFolds(dataDIR)
	# Count the number of classes.
	num_classes = len(classes)

	for i, (train_folders, test_folders) in enumerate(folds):
		print
		print 'Processing fold {0}/{1}'.format(i+1, len(folds))
		setName = 'fold-{0:02d}'.format(i+1)
		runNumber = i+1

		# Clean out the styleneruns.xml files to avoid errors.
		print 'Clearing stylenruns.xml'
		cleanRuns(styleneRUNS)

		print '--Train'
		runStylene(train_folders, setName, runNumber, num_classes, runType="train")
		if test_folders is not None:
			print '--Test'
			runStylene(test_folders, setName, runNumber, num_classes, runType="test")
			workflows = getWorkflow(styleneRUNS, setName, noTest=False)
		else:
			print '--Only one fold detected, not generating a test fold...'
			workflows = getWorkflow(styleneRUNS, setName, noTest=True)
		print '--Retrieving instance files...'
		getInstanceFiles(workflows, outputDIR, setName)
		print '--Done.'

def runStylene(TorT, setName, runNumber, num_classes,runType):
	'''
	First, remove existing material in UPLOADFILES and copy the TRAINING or TEST
	data to UPLOADFILES. Then, adapt the local startparameters.xml file and copy
	it to styleneRUN.
	Finally, run stylene and remove the data from styleneRUN/data again

	'''
	# First, remove material present in UPLOADFILES
	try:
		print '---Emptying uploadfiles directory...'
		x=[dir_util.remove_tree(os.path.join(UPLOADFILES,d)) for d in os.listdir(UPLOADFILES)]
	except:
		pass

	print '---Copying new directories...'
	for folder in TorT:
		dir_util.copy_tree(os.path.join(TorT, folder), os.path.join(UPLOADFILES, os.path.split(folder)[-1]))

	print '---Adapting XML...'
	adaptPARAMS(setName,runNumber,num_classes,runType)

	# Change the directory, or Stylene won't find its configuration file.'
	os.chdir(STYLENE)
	print '---Creating instances with Stylene...'
	process = subprocess.Popen(['java', '-jar', styleneJAR], stdout=subprocess.PIPE, stderr = subprocess.STDOUT)

	while True:
		out_line = process.stdout.readline()
		exit_code = process.poll()

		if (not out_line) and (exit_code is not None):
			break
		out_line = out_line.strip()
		if 'ERROR' in out_line:
			log.error(out_line)
			if 'Exiting...' in out_line:
				sys.exit('Stylene exited with an error!\n{0}'.format(out_line))
		else:
			log.debug(out_line)

def adaptPARAMS(setName, runNumber, num_classes, runType):
	'''
	Adapt the parameter file and copy it to styleneRUN.

	'''
	modPARAMS = os.path.splitext(PARAMS)[0] + '-mod.xml'
	tree = ElementTree()
	tree.parse(PARAMS)
	tree.find('run-type').text = str(runType)
	tree.find('run-number').text = str(runNumber)
	tree.find('set-name').text = str(setName)
	tree.find('number-of-classes').text = str(num_classes)
	tree.write(modPARAMS, encoding='utf-8')

	file_util.copy_file(modPARAMS, newPARAMS)

def cleanRuns(styleneRUNS):
	'''
	If you do not remove the previous runs from styleneRUNS, Stylene will produce
	ERRORS.

	'''
	tree = ElementTree()
	tree.parse(styleneRUNS)
	tree.getroot().clear()
	tree.write(styleneRUNS, encoding='utf-8')

def getWorkflow(styleneRUNS, setName, noTest=False):
	'''
	Retrieve workflow id for train and test. Example:

	<run>
		<type>TRAINING</type>
		<run-number>1</run-number>
		<set-name>fold-0</set-name>
		<date>6/22/11 11:26 AM</date>
		<workflow-map>stylenerun/data//Workflow_5e1cefa6-b730-425c-99fc-7e2cc0e1d9bd_TRAINING_1_fold-0</workflow-map>
		<url />
	</run>
	<run>
		<type>TEST</type>
		<run-number>1</run-number>
		<set-name>fold-0</set-name>
		<date>6/22/11 11:27 AM</date>
		<workflow-map>stylenerun/data//Workflow_2c1f86e0-bb05-4ab8-a6df-171c32d6def5_TEST_1_fold-0</workflow-map>
		<url></url>
	</run>

	'''
	tree = ElementTree()
	tree.parse(styleneRUNS)
	runs = tree.findall('run')
	if noTest:
		trainflow = runs[0]
		assert trainflow.find('type').text.lower() in ['train', 'training']
		trainflow, testflow = trainflow.find('workflow-map').text, None
	else:
		trainflow, testflow = zip(runs[::2], runs[1::2])[0]
		assert testflow.find('type').text.lower() in ['test', 'testing']
		assert trainflow.find('set-name').text == testflow.find('set-name').text == setName
		trainflow, testflow = trainflow.find('workflow-map').text, testflow.find('workflow-map').text

	return (trainflow, testflow)

def getInstanceFiles(workflows, destination, setName):
	'''
	Given a tuple of (train, test) workflow directories, retrieve the instance
	files and place them in <destination>.

	'''
	global overwrite_instances

	trainflow, testflow = workflows

	trainfolder = os.path.join(destination, setName, 'train')
	testfolder = None
	if testflow is not None:
		testfolder = os.path.join(destination, setName, 'test')

	for flow, folder in [(trainflow, trainfolder), (testflow, testfolder)]:
		if flow is not None:
			if not overwrite_instances:
				if os.path.exists(folder):
					overwrite = raw_input('\n{0} already exists. Are you sure you want to overwrite?\n([y]es/[n]o/[a]lways. Selecting "no" will terminate the script.)\n\n'.format(folder))
					while True:
						if overwrite.lower() in ['y', 'yes', 'n', 'no', 'a','always']:
							break
						overwrite = raw_input('\nPlease select one of the following options: [y]es/[n]o/[a]lways\n\n')
					if overwrite in ['a', 'always']:
						overwrite_instances = True
					elif overwrite in ['n', 'no']:
						sys.exit('Process terminated.')
			dir_util.copy_tree(os.path.join(flow, 'instances'), folder)

if __name__ == '__main__':

	parser = OptionParser(usage = '''

python %prog data_folder (options)

data_folder should be a directory containing the data structured in the
following way:

data_folder
	\_ fold-01
		\_ classA
			\_ doc1a.txt
			\_ doc2a.txt
			\_ ...
		\_ classB
			\_
		\_ ...
	\_ fold-02
		\_ classA
			\_ doc1b.txt
			\_ doc2b.txt
			\_ ...
		\_ classB
		\_ ...
	\_ ...

The "fold-\d+" pattern for the first-level subfolders is MANDATORY. The other
folders can take any name.
The text documents should be in a Stylene-ready format, i.e. one token per line.''', version='%prog 0.4')
	parser.add_option('-o', '--out-folder', dest='output_folder', default='instances',
						help="Specify the output folder in which the instances will be stored. (Default: in 'instances')")
	parser.add_option('-l', '--log-file', dest='log_file', default='stylene.log',
						help="Specify the location of the log file where output and errors will be written. (Default: stylene.log in the working directory.)")
	parser.add_option('-d', '--debug', dest='debug', default=False, action='store_true',
						help="Use this option for a much more verbose log.")
	parser.add_option('--stylene-path', dest='stylene_path', default='/opt/Stylene',
						help="Specify the path to Stylene. (Default: /opt/Stylene)")
	parser.add_option('--params-file', dest='params_file', default='startparameters.xml',
						help="Specify the path to Stylene's parameters XML. (Default: startparameters.xml")
	(options, args) = parser.parse_args()

	if len(args) != 1:
		sys.exit(parser.print_help())

	input_folder = args[0]
	output_folder = options.output_folder
	STYLENE = options.stylene_path
	styleneJAR	=	os.path.join(STYLENE, 'stylene.jar')
	assert os.path.exists(styleneJAR), 'stylene.jar not found!'
	styleneRUN	=	os.path.join(STYLENE, 'stylenerun')
	styleneRUNS	=	os.path.join(styleneRUN, 'styleneruns.xml')
	newPARAMS	=	os.path.join(styleneRUN, 'startparameters.xml')
	UPLOADFILES	=	os.path.join(styleneRUN, 'data/uploadfiles')
	PARAMS		=	os.path.abspath(options.params_file)

	LOG_FILENAME = options.log_file
	log = logging.getLogger('stylene-log')
	loghandler = logging.handlers.RotatingFileHandler(LOG_FILENAME, maxBytes=26214400)
	formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
	loghandler.setFormatter(formatter)
	log.addHandler(loghandler)
	if options.debug:
		log.setLevel(logging.DEBUG)
	else:
		log.setLevel(logging.WARNING)
	log.info('Log initialized.')

	main(input_folder, output_folder, )
