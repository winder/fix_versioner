#! /usr/bin/env python3

from git import Repo
import requests
import argparse
import re
import json
import sys
from datetime import datetime


def parse_args():
    """ Parse args and perform additional validation/initialization of computed arguments. """
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', required=False, help='Automates setting "--release-tag <app>-<timestamp>" and "--previous-tag <app>-*". ')
    parser.add_argument('--repo-path', required=True, help='Path to the repo being released.')
    parser.add_argument('--release-name', help='Release name to use in Jira, if not provided the --release-tag is used, or if --app is present a computed <app>-<date> is used.')
    parser.add_argument('--release-description', required=False, help='Optional description field used for the fix version.')
    parser.add_argument('--release-tag', required=False, help='Most recent tag for this release, if wildcards are included will use the most recent match. If not present the most recent commit will be used.')
    parser.add_argument('--previous-tag', required=False, help='Tag for the last release, if wildcards are included will use the most recent match. It is required if --app is not specified.')
    parser.add_argument('--jira-base-url', required=True, help='Root of your jira URL, like \'https://traackr.atlassian.net\'')
    parser.add_argument('--jira-username', required=True, help='Jira username.')
    parser.add_argument('--jira-password', required=True, help='Jira password.')
    parser.add_argument('--jira-project', required=True, default='CORE', help='Project to create fix version in.')
    parser.add_argument('--commit-pattern', default='^(?P<key>[\w]*-[\d]*)[ :-](?P<value>.*)', help='Regex pattern used to group commits, <key> and <value> identifiers may be used to specify group order. For example: \'(?P<key>CORE-[\d]*): (?P<value>.*)\' or \'(CORE-[\d]*: (.*)\' could be used for CORE.')
    parser.add_argument('--assume-yes', default=False, action='store_true', help='If prompted to continue, assume yes (i.e. there were invalid tickets, would you like to continue tagging valid tickets?).')
    parser.add_argument('--allow-multiple-versions', default=False, help='For some issues there may be changes in multiple applications, if you want a fix version per app use this flag.')
    parser.add_argument('--create-tag', required=False, action='store_true', help='Causes a new tag to be created using the value of --app and a timestamp.')
    parser.add_argument('--dry-run', default=True, help='Do not modify any data.')

    args = parser.parse_args()

    if args.app and args.release_tag:
        parser.error('Ambiguous release tag, must not provide --app and --release-tag.')

    if not args.app and not args.previous_tag:
        parser.error('One of --previous-tag or --app is required.')

    # Initialize tags for app.
    if args.app:
        # Timestamp format yyyy-mm-ddThh.mm.ssZ
        args.release_name = args.release_name or '%s-%s' % (args.app, datetime.now().strftime('%Y-%m-%dT%H.%M.%SZ'))
        args.previous_tag = args.previous_tag or '%s-*' % args.app

    if not args.release_name:
        parser.error('Missing required parameter, --app or --release-name must be provided.')

    return args


# http://stackoverflow.com/a/4690655/204023
def query_yes_no(question, default="yes"):
    """Ask a yes/no question via input() and return their answer.

    "question" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).

    The "answer" return value is True for "yes" or False for "no".
    """
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " [y/n] "
    elif default == "yes":
        prompt = " [Y/n] "
    elif default == "no":
        prompt = " [y/N] "
    else:
        raise ValueError("invalid default answer: '%s'" % default)

    while True:
        print(question + prompt, end='')
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            print("Please respond with 'yes' or 'no' (or 'y' or 'n').\n", end='')


def get_commits_for_tag(repo, first_tag, second_tag):
    """ Return commits between the two tags  using 'git log first...second' to fetch commits. """

    # --format=%s for ease of parsing.
    commits = repo.git.log('--format=%s', '{}...{}'.format(first_tag, second_tag))
    commits = commits.split('\n')
    return commits


def group_commits_by_pattern(regex_pattern, commit_messages):
    """ Group commits according to a pattern. In case pattern is not formatted 'key: message' group ids may be used. """
    key_id = 1
    value_id = 2

    if 'key' in regex_pattern.groupindex:
        key_id = regex_pattern.groupindex['key']
    if 'value' in regex_pattern.groupindex:
        value_id = regex_pattern.groupindex['value']

    commit_dict = {}
    unknown_commits = []
    for commit in commit_messages:
        # parse out JIRA id
        m = re.search(regex_pattern, commit)
        if m:
            key = m.group(key_id).strip().upper()
            if key not in commit_dict:
                commit_dict[key] = []

            commit_dict[key].append(m.group(value_id).strip())
        else:
            unknown_commits.append(commit.strip())

    return commit_dict, unknown_commits


def validate_jira_id(jira_id, allow_multiple_fix_versions, base_url, jira_username, jira_password):
    """ Throw an exception if the jira_id is invalid. Check jira to verify existence, done state and fix version. """

    request_url = base_url + '/rest/api/2/issue/' + jira_id
    response = requests.get(request_url, auth=(jira_username, jira_password))
    if response.status_code == 404:
        message = 'Jira ticket not found.'
        raise ValueError(message)

    if response.status_code != 200:
        message = 'Unexpected status code during lookup: {}'.format(response.status_code)
        raise ValueError(message)

    # parse response and check fields
    issue_json = json.loads(response.text)
    if issue_json['fields']['status']['name'] != 'Done':
        message = "Invalid status, expected 'Done' found '{}'".format(issue_json['fields']['status']['name'])
        raise ValueError(message)

    if not allow_multiple_fix_versions and 'fixVersions' in issue_json['fields'] and len(issue_json['fields']['fixVersions']) != 0:
        message = 'Already contains a fix version: {}'.format(issue_json['fields']['fixVersions'][0]['name'])
        raise ValueError(message)


def create_fix_version(fix_version_name, description, jira_project, base_url, jira_username, jira_password):
    """ Create a fix version in given project with given name, returns the fix version id or raises an exception. """
    post_data = {
        'name': fix_version_name,
        'project': jira_project,
        'released': True,
        'userReleaseDate': datetime.now().strftime('%d/%B/%Y')
    }

    if description:
        post_data['description'] = description

    response = requests.post(
        base_url + '/rest/api/2/version',
        headers={'content-type': 'application/json'},
        auth=(jira_username, jira_password),
        data=json.dumps(post_data))

    if response.status_code is not 201:
        raise ValueError('Failed to create fix version. Expected status 201, received {}'.format(response.status_code))
    status_response_json = json.loads(response.text)
    return status_response_json['id']


def add_fix_version_to_ticket(jira_id, fix_version_id, base_url, jira_username, jira_password):
    """ Add fix version to jira ticket. """
    post_data = {
        'update': {
            'fixVersions': [
                {
                    'add': {
                        'id': fix_version_id
                    }
                }
            ]
        }
    }

    response = requests.put(
        base_url + '/rest/api/2/issue/' + jira_id,
        headers={'content-type': 'application/json'},
        auth=(jira_username, jira_password),
        data=json.dumps(post_data))

    if response.status_code is not 204:
        raise ValueError('Failed to add fix version to {}. Expected status 204, received {}'.format(jira_id, response.status_code))


def resolve_tag(repo, tag):
    """ Given a tag with optional wildcards, returns the most recent match. """

    if not tag:
        return ""

    # Find tags
    tags = repo.tags
    sorted_tags = sorted(tags, key=lambda tag_to_sort: tag_to_sort.commit.committed_date, reverse=True)

    p = re.compile(tag)
    for t in sorted_tags:
        if p.match(t.name):
            return t

    raise Exception('Could not find tag: %s' % tag)


def main():
    args = parse_args()

    print('\nrelease: %s\nprevious: %s' % (args.release_tag, args.previous_tag))

    repo = Repo.init(args.repo_path)
    pattern = re.compile(args.commit_pattern)

    # Grab commits
    release = resolve_tag(repo, args.release_tag)
    previous = resolve_tag(repo, args.previous_tag)
    print('\nrelease: %s\nprevious: %s' % (release, previous))
    print('\nLooking up unique issues in range: {} ... {}'.format(release, previous))
    commits = get_commits_for_tag(repo, release, previous)

    # Group by pattern
    grouped_commits, unknown_commits = group_commits_by_pattern(pattern, commits)

    # Sort by number of commits for fun
    # my_sorted = sorted(grouped_commits.items(), key=lambda item: len(item[1]), reverse=True)
    # for key, value in my_sorted:
    #     print('{}, {} commits: {}'.format(key, len(value), value))
    #     is_valid_jira_id(key, args.jira_username, args.jira_password)

    print('\n=======================================================')
    print('= Came across some commits which couldn\'t be parsed: =')
    print('=======================================================\n')

    for commit in unknown_commits:
        print(commit)

    valid_tickets = {}
    invalid_tickets = {}

    # Validate tickets:
    print('\nValidating {} jira tickets: {}'.format(len(grouped_commits), ', '.join(grouped_commits.keys())))
    for jira_id, commit_list in grouped_commits.items():
        try:
            validate_jira_id(jira_id, args.allow_multiple_versions, args.jira_base_url, args.jira_username, args.jira_password)
            valid_tickets[jira_id] = commit_list
        except ValueError as e:
            invalid_tickets[jira_id] = (commit_list, str(e))

    if len(valid_tickets) != 0:
        print('\nThe following valid tickets were discovered:\n')
        for ticketId, commits in valid_tickets.items():
            print('{} is ready to tag with {} commits.'.format(ticketId, len(commits)))

    if len(invalid_tickets) != 0:
        print('\n=================================================')
        print('= The following invalid tickets were discovered =')
        print('=================================================\n')
        # Sort by error message:
        for ticketId, commitErrorTuple in sorted(invalid_tickets.items(), key=lambda item: item[1][1]):
            print('{} is invalid: {}'.format(ticketId, commitErrorTuple[1]))

        print('')

    # Early exit.
    if len(valid_tickets) == 0:
        print('There were no valid tickets to release, exiting.')
        sys.exit(-1)

    if args.dry_run:
        print('Done releasing {}! (dry run exit)'.format(args.release_name))
        sys.exit(-1)

    if args.assume_yes is False and not query_yes_no('Would you like to continue tagging valid tickets?'):
        sys.exit(-1)

    # Create fix version.
    fix_version_id = create_fix_version(args.release_name, args.description, args.jira_project, args.jira_base_url, args.jira_username, args.jira_password)

    # Apply fix version to tickets.
    for item in valid_tickets.items():
        try:
            add_fix_version_to_ticket(item[0], fix_version_id, args.jira_base_url, args.jira_username, args.jira_password)
        except ValueError as e:
            print('Failure setting fix version for {}: {}'.format(item[0], str(e)))

    # Create and push a tag if requested
    if args.create_tag and valid_tickets:
        new_tag = repo.create_tag(args.release_name, message='Automated tag.')
        repo.remotes.origin.push(new_tag)

    # Release notes summary?
    print('Done releasing {}!'.format(args.release_name))


# Kick off the main function
if __name__ == '__main__':
    main()
