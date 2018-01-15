#!/bin/bash

if [ -z "$PROJECT_DIR" ]; then
   echo "PROJECT_DIR is not set"
   exit -1
fi
if ! [ -d "$PROJECT_DIR" ]; then
   echo "PROJECT_DIR is not a valid directory: $PROJECT_DIR"
   exit -1
fi
if [ -z "$DATA_DIR" ]; then
   echo "DATA_DIR is not set"
   exit -1
fi
if ! [ -d "$DATA_DIR" ]; then
   echo "DATA_DIR is not a valid directory: $DATA_DIR"
   exit -1
fi

echo "Update ClusterOne"
pip install --upgrade clusterone

# set PROJECT_DIR and DATA_DIR in case they are relative routes
PWD=$(pwd -P)
cd $PROJECT_DIR
PROJECT_DIR=$(pwd -P)
cd $PWD
cd $DATA_DIR
DATA_DIR=$(pwd -P)
cd $PWD

echo "Push the project to ClusterOne"
cd $PROJECT_DIR
git push clusterone master
if [ $? -ne 0 ]
then
   echo "Couldn't push the project to ClusterOne"
   exit $?
fi
echo "Push the data to ClusterOne"
cd $DATA_DIR
git push clusterone master
if [ $? -ne 0 ]
then
   echo "Couldn't push the data to ClusterOne"
   exit $?
fi
echo "Create job in ClusterOne"
just create job
if [ $? -ne 0 ]
then
   echo "Couldn't create a job in ClusterOne"
   exit $?
fi

cd $PWD