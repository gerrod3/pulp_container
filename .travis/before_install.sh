#!/usr/bin/env bash

# WARNING: DO NOT EDIT!
#
# This file was generated by plugin_template, and is managed by it. Please use
# './plugin-template --travis pulp_container' to update this file.
#
# For more info visit https://github.com/pulp/plugin_template

set -mveuo pipefail

mkdir .travis/vars || true
echo "---" > .travis/vars/main.yaml

export PRE_BEFORE_INSTALL=$TRAVIS_BUILD_DIR/.travis/pre_before_install.sh
export POST_BEFORE_INSTALL=$TRAVIS_BUILD_DIR/.travis/post_before_install.sh

COMMIT_MSG=$(git log --format=%B --no-merges -1)
export COMMIT_MSG

if [ -f $PRE_BEFORE_INSTALL ]; then
  source $PRE_BEFORE_INSTALL
fi

if [[ -n $(echo -e $COMMIT_MSG | grep -P "Required PR:.*" | grep -v "https") ]]; then
  echo "Invalid Required PR link detected in commit message. Please use the full https url."
  exit 1
fi

if [ "$TRAVIS_PULL_REQUEST" != "false" ] || [ -z "$TRAVIS_TAG" -a "$TRAVIS_BRANCH" != "master" ]
then
  export PULPCORE_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulpcore\/pull\/(\d+)' | awk -F'/' '{print $7}')
  export PULP_SMASH_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp-smash\/pull\/(\d+)' | awk -F'/' '{print $7}')
  export PULP_OPENAPI_GENERATOR_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp-openapi-generator\/pull\/(\d+)' | awk -F'/' '{print $7}')
  echo $COMMIT_MSG | sed -n -e 's/.*CI Base Image:\s*\([-_/[:alnum:]]*:[-_[:alnum:]]*\).*/ci_base: "\1"/p' >> .travis/vars/main.yaml
else
  export PULPCORE_PR_NUMBER=
  export PULP_SMASH_PR_NUMBER=
  export PULP_OPENAPI_GENERATOR_PR_NUMBER=
  export CI_BASE_IMAGE=
fi

# dev_requirements contains tools needed for flake8, etc.
# So install them here rather than in install.sh
pip install -r dev_requirements.txt

# check the commit message
./.travis/check_commit.sh

# run black separately from flake8 to get a diff
black --version
black --check --diff .

# Lint code.
flake8 --config flake8.cfg

# check for imports from pulpcore that aren't pulpcore.plugin
./.travis/check_pulpcore_imports.sh

cd ..

git clone https://github.com/pulp/pulp-openapi-generator.git
if [ -n "$PULP_OPENAPI_GENERATOR_PR_NUMBER" ]; then
  cd pulp-openapi-generator
  git fetch origin pull/$PULP_OPENAPI_GENERATOR_PR_NUMBER/head:$PULP_OPENAPI_GENERATOR_PR_NUMBER
  git checkout $PULP_OPENAPI_GENERATOR_PR_NUMBER
  cd ..
fi

cd pulp-openapi-generator
sed -i -e 's/localhost:24817/pulp/g' generate.sh
sed -i -e 's/:24817/pulp/g' generate.sh
cd ..

git clone --depth=1 https://github.com/pulp/pulpcore.git --branch 3.7

cd pulpcore
if [ -n "$PULPCORE_PR_NUMBER" ]; then
  git fetch --depth=1 origin pull/$PULPCORE_PR_NUMBER/head:$PULPCORE_PR_NUMBER
  git checkout $PULPCORE_PR_NUMBER
fi
cd ..



# When building a (release) tag, we don't need the development modules for the
# build (they will be installed as dependencies of the plugin).
if [ -z "$TRAVIS_TAG" ]; then

  git clone --depth=1 https://github.com/pulp/pulp-smash.git

  if [ -n "$PULP_SMASH_PR_NUMBER" ]; then
    cd pulp-smash
    git fetch --depth=1 origin pull/$PULP_SMASH_PR_NUMBER/head:$PULP_SMASH_PR_NUMBER
    git checkout $PULP_SMASH_PR_NUMBER
    cd ..
  fi

  # pulp-smash already got installed via test_requirements.txt
  pip install --upgrade --force-reinstall ./pulp-smash

fi


# Intall requirements for ansible playbooks
pip install docker netaddr boto3 ansible

ansible-galaxy collection install amazon.aws

cd pulp_container

if [ -f $POST_BEFORE_INSTALL ]; then
  source $POST_BEFORE_INSTALL
fi
