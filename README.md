## Git↔Jira Release Integration

Command line script used to analyze git commits/tags, parse out Jira ticket IDs, create Jira fix versions then update tickets with their fix version. It is designed in such a way that it can be run as an automatic step during one click deployments.

#### Requirements:
* Commit messages which contain their corresponding ticket ID. For example `TRAACKR-1234: Fixed a bug`.
* A tag for every release.
* Python 3
* Install dependencies in requirements.txt, `pip install -r requirements.txt`


## Usage

#### Arguments

| command | description |
| ------- | ----------- |
| --app | Optional app name, this is used as a helper to set the `--release-name` and `--previous-tag`. |
| --repo-path | Path to git repository |
| --release-name | Optional release name to use, if not provided the `--release-tag` is used, or if `--app` is present a computed <app>-<date> is used. |
| --release-tag | Most recent tag, start bound for commits included in release. |
| --previous-tag | Oldest tag, end bound for commits included in release. |
| --jira-base-url | Root of your jira URL, like such as `https://traackr.atlassian.net` |
| --jira-username | Login for Jira REST API. |
| --jira-password | Password for Jira REST API. |
| --jira-project | Jira project to use. |
| --commit-pattern | Regular expression using python syntax for parsing commit messages. Use `key` and `value` named groups for the Jira ticket id `key` pattern and commit message `value`. |
| --assume-yes | If provided any prompts will be defaulted to `yes`. Default value is `False`. |
| --allow-multiple-versions | Allow multiple fix versions on a single ticket. For some projects it may be desirable to have multiple fix versions attached to a single ticket. For instance a library and consumer are both modified for one feature. Default value is `False`. |
| --create-tag | This flag indicates whether or not to tag the repository with the `--release-name` after finishing.
| --dry-run | Prevents Jira modifications. Default value is `True`. |

#### example command

## Release an app
This style command is for integrating with a CI tool. All commits from the most recent until the next tag matching `skynet-*` will be considered. Those which match the commit-pattern will be validated in Jira and tagged with a fix version.
```
./release_fix_versioner.py
       --dry-run false
       --app skynet
       --create-tag
       --repo-path ~/skynet/
       --jira-base-url cyberdyne-systems.atlassian.net
       --jira-username cyberdyne
       --jira-password cyberdyne1997
       --jira-project SNAI
       --commit-pattern "(?P<key>[\w]*-[\d]*)[ :-](?P<value>.*)"
```

## Release between two tags.
This is typically done as a post-release step when releases involve a tag. In this example all commits between `rev-1.49` and `rev-1.50` are considered. Those which match the commit-pattern will be validated in Jira and tagged with a fix version.
```
./release_fix_versioner.py
       --dry-run false
       --release-name "1.50 - Stemming sentience"
       --repo-path ~/skynet/
       --release-tag rev-1.50
       --previous-tag rev-1.49
       --jira-base-url cyberdyne-systems.atlassian.net
       --jira-username cyberdyne
       --jira-password cyberdyne1997
       --jira-project SNAI
       --commit-pattern "(?P<key>[\w]*-[\d]*)[ :-](?P<value>.*)"
```

#### example output

```shell
Looking up unique issues in range: rev-1.54 ... rev-1.53

=======================================================
= Came across some commits which couldn't be parsed: =
=======================================================

Merge branch 'release/1.54'
updating poms for 1.54 release
updating poms for 1.54 release
Merged in tracking-fields (pull request #115)
CORE-NoOp: Spring stuff for the facebook changes also.
CORE-NoOp: Testing spring config for refresh beans.
Gitflow: Prepping for release
CORE-NoOp: Testing spring config for refresh beans.
CORE-NoOp: Testing spring config for refresh beans.
CORE-NoOp: Testing spring config for refresh beans.
Merge branch 'dvlp' of bitbucket.org:traackr/core-tracking-broker into dvlp
CORE-NoOp: Testing spring config for refresh beans.
Merged dvlp into CORE-3376
CORE-NoOp: Testing spring config for refresh beans.
CORE-NoOp: Testing spring config for refresh beans.
CORE-NoOp: Testing spring config for refresh beans.
CORE-NoOp: Testing spring config for refresh beans.
Merged dvlp into CORE-3376
Merge branch 'CORE-3376' of bitbucket.org:traackr/core-tracking-broker into CORE-3376
Merge branch 'dvlp' into CORE-3376
Merged in refresh-create (pull request #117)
Merged dvlp into CORE-3376
updating poms for 1.54-SNAPSHOT development
Merge branch 'release/1.53' into dvlp

Validating 7 jira tickets: CORE-3724, CORE-3625, CORE-3376, CORE-3428, CORE-3438, CPRE-3376, CORE-3154

The following valid tickets were discovered:

CORE-3724 is ready to tag with 17 commits.
CORE-3376 is ready to tag with 9 commits.
CORE-3428 is ready to tag with 5 commits.
CORE-3438 is ready to tag with 1 commits.
CORE-3154 is ready to tag with 1 commits.

=================================================
= The following invalid tickets were discovered =
=================================================

CORE-3625 is invalid: Already contains a fix version: 6.46 - Metrics Tracking; Tracking fields cleanup
CPRE-3376 is invalid: Jira ticket not found.

Would you like to continue tagging valid tickets? [Y/n] Y
Adding fix version to CORE-3724
Adding fix version to CORE-3376
Adding fix version to CORE-3428
Adding fix version to CORE-3438
Adding fix version to CORE-3438
Adding fix version to CORE-3154
All done!
```

