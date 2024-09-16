#!/usr/local/bin/python3
#
# sonar-tools
# Copyright (C) 2022-2024 Olivier Korach
# mailto:olivier.korach AT gmail DOT com
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#
"""
    Exports SonarQube platform configuration as JSON
"""
import sys
import json
import yaml

from cli import options
from sonar import exceptions, errcodes, utilities
import sonar.logging as log
from sonar import platform, rules, qualityprofiles, qualitygates, users, groups
from sonar import projects, portfolios, applications

_EVERYTHING = [
    options.WHAT_SETTINGS,
    options.WHAT_USERS,
    options.WHAT_GROUPS,
    options.WHAT_GATES,
    options.WHAT_RULES,
    options.WHAT_PROFILES,
    options.WHAT_PROJECTS,
    options.WHAT_APPS,
    options.WHAT_PORTFOLIOS,
]

__JSON_KEY_PLATFORM = "platform"

__JSON_KEY_SETTINGS = "globalSettings"
__JSON_KEY_USERS = "users"
__JSON_KEY_GROUPS = "groups"
__JSON_KEY_GATES = "qualityGates"
__JSON_KEY_RULES = "rules"
__JSON_KEY_PROFILES = "qualityProfiles"
__JSON_KEY_PROJECTS = "projects"
__JSON_KEY_APPS = "applications"
__JSON_KEY_PORTFOLIOS = "portfolios"

__MAP = {
    options.WHAT_SETTINGS: __JSON_KEY_SETTINGS,
    options.WHAT_USERS: __JSON_KEY_USERS,
    options.WHAT_GROUPS: __JSON_KEY_GROUPS,
    options.WHAT_GATES: __JSON_KEY_GATES,
    options.WHAT_RULES: __JSON_KEY_RULES,
    options.WHAT_PROFILES: __JSON_KEY_PROFILES,
    options.WHAT_PROJECTS: __JSON_KEY_PROJECTS,
    options.WHAT_APPS: __JSON_KEY_APPS,
    options.WHAT_PORTFOLIOS: __JSON_KEY_PORTFOLIOS,
}


def __parse_args(desc):
    parser = options.set_common_args(desc)
    parser = options.set_key_arg(parser)
    parser = options.set_output_file_args(parser, allowed_formats=("json", "yaml"))
    parser = options.add_thread_arg(parser, "project export")
    parser = options.set_what(parser, what_list=_EVERYTHING, operation="export or import")
    parser = options.add_import_export_arg(parser, "configuration")
    parser.add_argument(
        "--fullExport",
        required=False,
        default=False,
        action="store_true",
        help="Also exports informative data that would be ignored as part of an import. Informative field are prefixed with _."
        "This option is ignored in case of import",
    )
    parser.add_argument(
        "--exportDefaults",
        required=False,
        default=False,
        action="store_true",
        help="Also exports settings values that are the platform defaults. "
        f"By default the export will show the value as '{utilities.DEFAULT}' "
        "and the setting will not be imported at import time",
    )
    parser.add_argument(
        "--dontInlineLists",
        required=False,
        default=False,
        action="store_true",
        help="By default, sonar-config exports multi-valued settings as comma separated strings instead of arrays (if there is not comma in values). "
        "Set this flag if you want to force export multi valued settings as arrays",
    )
    args = options.parse_and_check(parser=parser, logger_name="sonar-config")
    return args


def __export_config(endpoint: platform.Platform, what: list[str], **kwargs) -> None:
    """Exports a platform configuration in a JSON file"""
    export_settings = {
        "INLINE_LISTS": not kwargs["dontInlineLists"],
        "EXPORT_DEFAULTS": kwargs["exportDefaults"],
        "FULL_EXPORT": kwargs["fullExport"],
        "THREADS": kwargs[options.NBR_THREADS],
    }
    if "projects" in what and kwargs[options.KEYS]:
        non_existing_projects = [key for key in kwargs[options.KEYS] if not projects.exists(key, endpoint)]
        if len(non_existing_projects) > 0:
            utilities.exit_fatal(f"Project key(s) '{','.join(non_existing_projects)}' do(es) not exist", errcodes.NO_SUCH_KEY)

    log.info("Exporting configuration from %s", kwargs[options.URL])
    key_list = kwargs[options.KEYS]
    sq_settings = {}
    sq_settings[__JSON_KEY_PLATFORM] = endpoint.basics()
    if options.WHAT_SETTINGS in what:
        sq_settings[__JSON_KEY_SETTINGS] = endpoint.export(export_settings=export_settings)
    if options.WHAT_RULES in what:
        sq_settings[__JSON_KEY_RULES] = rules.export(endpoint, export_settings=export_settings)
    if options.WHAT_PROFILES in what:
        if options.WHAT_RULES not in what:
            sq_settings[__JSON_KEY_RULES] = rules.export(endpoint, export_settings=export_settings)
        sq_settings[__JSON_KEY_PROFILES] = qualityprofiles.export(endpoint, export_settings=export_settings)
    if options.WHAT_GATES in what:
        sq_settings[__JSON_KEY_GATES] = qualitygates.export(endpoint, export_settings=export_settings)
    if options.WHAT_PROJECTS in what:
        sq_settings[__JSON_KEY_PROJECTS] = projects.export(endpoint, key_list=key_list, export_settings=export_settings)
    if options.WHAT_APPS in what:
        try:
            sq_settings[__JSON_KEY_APPS] = applications.export(endpoint, key_list=key_list, export_settings=export_settings)
        except exceptions.UnsupportedOperation as e:
            log.warning(e.message)
    if options.WHAT_PORTFOLIOS in what:
        try:
            sq_settings[__JSON_KEY_PORTFOLIOS] = portfolios.export(endpoint, key_list=key_list, export_settings=export_settings)
        except exceptions.UnsupportedOperation as e:
            log.warning(e.message)
    if options.WHAT_USERS in what:
        sq_settings[__JSON_KEY_USERS] = users.export(endpoint, export_settings=export_settings)
    if options.WHAT_GROUPS in what:
        sq_settings[__JSON_KEY_GROUPS] = groups.export(endpoint, export_settings=export_settings)

    sq_settings = utilities.remove_empties(sq_settings)
    if not kwargs["dontInlineLists"]:
        sq_settings = utilities.inline_lists(sq_settings, exceptions=("conditions",))
    with utilities.open_file(kwargs["file"]) as fd:
        if kwargs[options.FORMAT] == "yaml":
            print(yaml.dump(sq_settings), file=fd)
        else:
            print(utilities.json_dump(sq_settings), file=fd)
    log.info("Exporting configuration from %s completed", kwargs["url"])


def __import_config(endpoint: platform.Platform, what: list[str], **kwargs) -> None:
    """Imports a platform configuration from a JSON file"""
    log.info("Importing configuration to %s", kwargs[options.URL])
    key_list = kwargs[options.KEYS]
    try:
        with open(kwargs[options.REPORT_FILE], "r", encoding="utf-8") as fd:
            data = json.loads(fd.read())
    except FileNotFoundError as e:
        utilities.exit_fatal(f"OS error while reading file: {e}", exit_code=errcodes.OS_ERROR)
    if options.WHAT_GROUPS in what:
        groups.import_config(endpoint, data)
    if options.WHAT_USERS in what:
        users.import_config(endpoint, data)
    if options.WHAT_GATES in what:
        qualitygates.import_config(endpoint, data)
    if options.WHAT_RULES in what:
        rules.import_config(endpoint, data)
    if options.WHAT_PROFILES in what:
        if options.WHAT_RULES not in what:
            rules.import_config(endpoint, data)
        qualityprofiles.import_config(endpoint, data)
    if options.WHAT_SETTINGS in what:
        endpoint.import_config(data)
    if options.WHAT_PROJECTS in what:
        projects.import_config(endpoint, data, key_list=key_list)
    if options.WHAT_APPS in what:
        try:
            applications.import_config(endpoint, data, key_list=key_list)
        except exceptions.UnsupportedOperation as e:
            log.warning(e.message)
    if options.WHAT_PORTFOLIOS in what:
        try:
            portfolios.import_config(endpoint, data, key_list=key_list)
        except exceptions.UnsupportedOperation as e:
            log.warning(e.message)
    log.info("Importing configuration to %s completed", kwargs[options.URL])


def main() -> None:
    """Main entry point for sonar-config"""
    start_time = utilities.start_clock()
    try:
        kwargs = utilities.convert_args(__parse_args("Extract SonarQube platform configuration"))
        endpoint = platform.Platform(**kwargs)
        endpoint.verify_connection()
    except (options.ArgumentsError, exceptions.ObjectNotFound) as e:
        utilities.exit_fatal(e.message, e.errcode)
    if not kwargs[options.EXPORT] and not kwargs[options.IMPORT]:
        utilities.exit_fatal(f"One of --{options.EXPORT} or --{options.IMPORT} option must be chosen", exit_code=errcodes.ARGS_ERROR)

    what = utilities.check_what(kwargs.pop(options.WHAT, None), _EVERYTHING, "exported or imported")
    kwargs[options.FORMAT] = utilities.deduct_format(kwargs[options.FORMAT], kwargs[options.REPORT_FILE], allowed_formats=("json", "yaml"))
    if kwargs[options.EXPORT]:
        try:
            __export_config(endpoint, what, **kwargs)
        except exceptions.ObjectNotFound as e:
            utilities.exit_fatal(e.message, errcodes.NO_SUCH_KEY)
        except (PermissionError, FileNotFoundError) as e:
            utilities.exit_fatal(f"OS error while exporting config: {e}", exit_code=errcodes.OS_ERROR)
    if kwargs["import"]:
        if kwargs["file"] is None:
            utilities.exit_fatal("--file is mandatory to import configuration", errcodes.ARGS_ERROR)
        __import_config(endpoint, what, **kwargs)
    utilities.stop_clock(start_time)
    sys.exit(0)


if __name__ == "__main__":
    main()
