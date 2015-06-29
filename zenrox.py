#!/usr/bin/env python2

from __future__ import print_function

from suds.client import Client
from bunch import Bunch
import requests

from collections import OrderedDict
import datetime as DT
import urllib
import json
import logging
import os

DEBUG = False

MOBAPI = 'https://m.tenrox.net/2014R3/tenterprise/api/'

def log(msg, *args):
    print(msg % args)

def getclient(org, svc):
    url = 'https://{}.tenrox.net/TWebService/{}.svc?singleWsdl'.format(org, svc)
    client = Client(url)
    # Tenrox forces a redirect to https, but the wsdl says http connection.
    # Unfortunately this redirection doesn't work with suds. This is a magic
    # option which apparently overrides the location in the wsdl.
    client.options.location = url
    return client

def weekstart(date):
    return date - DT.timedelta(days=date.weekday())

services = [
    'LogonAs',

    'Assignments',
    #'BusinessUnits',
    #'ChargeEntries',
    #'Clients',
    #'ClientInvoices',
    #'ClientInvoiceOptions',
    #'Contact',
    #'Currencies',
    #'CustomFields',
    #'ExecuteStoredProcedure',
    #'ExpenseEntries',
    #'ExpenseItems',
    #'ExpenseReports',
    #'Groups',
    #'MapData',
    #'Milestones',
    #'Notes',
    #'Projects',
    #'Sites',
    #'Skills',
    #'Tasks',
    #'TaxGroupDetails',
    #'TaxGroups',
    #'TimeEntries',
    'Timesheets',
    #'Users',
    #'Worktypes',
]

class Assignment(object):

    keys = set(['AccessType', 'ActionType', 'ActualWorkHours', 'AssignCompleted', 'AssignmentName', 'ClientName', 'ClientUniqueId', 'CurrentTimeBudget', 'Custom1', 'DirtyStatus', 'ElapsedTime', 'EmailAddress', 'EnableEtc', 'EndDate', 'Etc', 'EtcEndDate', 'EtcStartDate', 'FirstName', 'IsBillable', 'IsFunded', 'IsLeaveTime', 'IsOverHead', 'IsPayable', 'IsRandD', 'LastName', 'LastTimeEntryDate', 'Note', 'ProjectId', 'ProjectManagerFullName', 'ProjectManagerID', 'ProjectName', 'ProjectSchedId', 'ProjectScheduling', 'QueryLevel', 'ShowAssignment', 'ShowETC', 'StartDate', 'TaskColor', 'TaskName', 'TaskUniqueId', 'TimeEntries', 'UniqueId', 'UserId', 'UserIdNo', 'WorkTypeName', 'WorkTypeUniqueId', 'WorkflowEntryId'])

    def __init__(self, obj, *args, **kwargs):
        super(Assignment, self).__init__(*args, **kwargs)
        assert obj.__class__.__name__ == 'Assignment'
        assert set([kv[0] for kv in obj]) == self.keys
        self._obj = obj

        assert obj.AccessType == 1
        assert obj.IsLeaveTime is False

        self.uid = obj.UniqueId
        self.project_id = obj.ProjectId
        self.project_name = obj.ProjectName
        self.task_id = obj.TaskUniqueId
        self.task_name = obj.TaskName

class AssignmentAttr(object):

    keys = set(['AccessType', 'AssignmentComp', 'AssignmentName', 'AssignmentUid', 'BusinessUnitName', 'BusinessUnitUid', 'ChargeName', 'ChargeUid', 'ClientName', 'ClientUid', 'ComponentName', 'ComponentUid', 'Dirty', 'ETC', 'ETCChanged', 'EndDate', 'HasTimeEntry', 'IsBillable', 'IsCustom', 'IsDefault', 'IsETCEditable', 'IsFunded', 'IsNonWorkingTime', 'IsPayable', 'IsRandD', 'ManagerUid', 'PercentComplete', 'PhaseName', 'PhaseUid', 'PortfolioName', 'PortfolioUid', 'ProductName', 'ProductUid', 'ProjectName', 'ProjectUid', 'ShowETC', 'SiteName', 'SiteUid', 'StartDate', 'TaskName', 'TaskUid', 'TeamName', 'TeamUid', 'TemplateUid', 'TitleName', 'TitleUid', 'UniqueID', 'UserGroupName', 'UserGroupUid', 'UserUid', 'WorkTypeName', 'WorkTypeUid'])

    def __init__(self, obj, *args, **kwargs):
        super(AssignmentAttr, self).__init__(*args, **kwargs)
        assert obj.__class__.__name__ == 'AssignmentAttribute'
        assert set([kv[0] for kv in obj]) == self.keys
        self._obj = obj

        assert obj.HasTimeEntry is True
        assert obj.AccessType == 1
        assert obj.IsNonWorkingTime is False

        self.uid = obj.UniqueID
        self.assignment_id = obj.AssignmentUid

class Entry(object):

    keys = set(['Approved', 'AssignmentAttributeUid', 'AssignmentUid', 'BUnitUid', 'Billed', 'ChargeUid', 'CreatedByUid', 'CreationDate', 'DoubleOvertime', 'EntryDate', 'EntryState', 'HasNotes', 'IsBillable', 'IsCustom', 'IsDirty', 'IsFunded', 'IsNonWorking', 'IsPayable', 'IsRandD', 'Overtime', 'PhaseUid', 'Posted', 'RegularTime', 'Rejected', 'SiteName', 'SiteUid', 'TaskUid', 'TimeEntryNotes', 'TimesheetUid', 'TotalTime', 'UniqueID', 'UpdateDate', 'UpdatedByUid', 'UserUid', 'hasError'])

    def __init__(self, obj, *args, **kwargs):
        super(Entry, self).__init__(*args, **kwargs)
        assert obj.__class__.__name__ == 'TimesheetEntry'
        assert set([kv[0] for kv in obj]) == self.keys
        self._obj = obj

        assert obj.IsNonWorking is not True # TODO
        assert obj.TotalTime == obj.RegularTime + obj.Overtime + obj.DoubleOvertime

        self.uid = obj.UniqueID
        self.note = None
        self.assignment_id = obj.AssignmentUid
        self.assignment_attr_id = obj.AssignmentAttributeUid
        self.date = DT.datetime.strptime(obj.EntryDate, '%m/%d/%Y').date()
        self.time = DT.timedelta(seconds=obj.TotalTime)

        if obj.TimeEntryNotes is not None:
            subobjs = obj.TimeEntryNotes.TimesheetNote
            assert len(subobjs) == 1
            self.note = subobjs[0].Description

class Timesheet(object):

    keys = set(['ActiveSiteUid', 'ActivityGUID', 'AllowEntryInTheAdvance', 'AllowEntryInTheAdvanceType', 'AllowEntryInThePast', 'AllowEntryInThePastType', 'BankedOverTime', 'CanManagerModifyBillable', 'CanManagerModifyPayable', 'DefaultClientUid', 'DefaultProjectUid', 'DefaultWorkTypeUid', 'Details', 'EmployeeType', 'EndDate', 'FunctionalGroupUid', 'FunctionalManagerUid', 'HasAssignments', 'HasErrors', 'HasNotes', 'HasTimeentries', 'HireDate', 'IsTimesheetClosed', 'LeaveTimes', 'LockedDates', 'MasterSiteUid', 'PeriodClosed', 'PersonalDayTime', 'ResourceType', 'RoleObjectType', 'ShowAdjustmentsSection', 'ShowAssignmentsSection', 'ShowLeaveTimeSection', 'ShowNonWorkingTimeSection', 'SickLeaveTime', 'StartDate', 'TemplateName', 'TemplateUid', 'TerminatedDate', 'TimeIncrement', 'TimesheetAssignmentAttributes', 'TimesheetColumns', 'TimesheetEntries', 'TimesheetErrors', 'TimesheetNotes', 'TimesheetStates', 'TimesheetTransitions', 'TotalPeriodOverTime', 'TotalPeriodPayableTime', 'TotalPeriodRegTime', 'UniqueId', 'UserAccessStatus', 'UserFirstName', 'UserID', 'UserLastName', 'UserType', 'UserUID', 'UsersAccessStatus', 'VacationTime', 'WorkflowGUID'])

    def __init__(self, weekdate, obj, *args, **kwargs):
        super(Timesheet, self).__init__(*args, **kwargs)
        assert obj.__class__.__name__ == 'Timesheet'
        assert set([kv[0] for kv in obj]) == self.keys
        self._obj = obj

        assert weekstart(weekdate) == weekdate

        self.uid = obj.UniqueId
        self.startdate = weekdate
        self.entries = OrderedDict()
        self.assignment_attrs = OrderedDict()

        if obj.TimesheetEntries is not None:
            for subobj in obj.TimesheetEntries.TimesheetEntry:
                assert subobj.IsNonWorking in [True, False]
                if subobj.IsNonWorking:
                    continue # TODO: don't skip
                self.entries[subobj.UniqueID] = Entry(subobj)
        if obj.TimesheetAssignmentAttributes is not None:
            for subobj in obj.TimesheetAssignmentAttributes.AssignmentAttribute:
                assert subobj.IsNonWorkingTime in [True, False]
                if subobj.IsNonWorkingTime:
                    continue # TODO: don't skip
                self.assignment_attrs[subobj.UniqueID] = AssignmentAttr(subobj)

clients = Bunch()

def init():
    global DEBUG
    if os.environ.get('DEBUG', '0') == '1':
        DEBUG = True
    if DEBUG:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger('suds.client').setLevel(logging.DEBUG)
        logging.getLogger('requests.packages').setLevel(logging.DEBUG)
    org, username, password = open('.tenacct').read().strip().split(':')
    log('Initialising services')
    for service in services:
        clients[service] = getclient(org, service)
    log('Logging into %s tenrox as %s', org, username)
    auth = clients.LogonAs.service.Authenticate(org, username, password, '', True)
    resp = requests.get(MOBAPI + 'Security', auth=(org + ':' + username, password))
    assert resp.status_code == 200
    mobauth = json.loads(resp.text)['Token'] # this is base64 encoded xml...
    userid = auth.UniqueId
    return userid, auth, mobauth

def get_timesheet(auth, userid, weekdate):
    log('Getting timesheet for week starting %s', weekdate.isoformat())
    tss = clients.Timesheets.service.QueryTimesheetsDetailsTyped(auth, userid, weekdate)
    mytss = tss.MyTimesheets
    assert len(mytss.Timesheet) == 1
    return Timesheet(weekdate, mytss.Timesheet[0])

def get_assignments(auth, userid, weekdate):
    log('Getting assignments for week starting %s', weekdate.isoformat())
    assert weekstart(weekdate) == weekdate
    weekend = weekdate + DT.timedelta(days=6)
    aoa = clients.Assignments.service.QueryByUserIdTyped(auth, userid, weekdate.isoformat(), weekend.isoformat())
    assignments = OrderedDict()
    for assignment in aoa.Assignment:
        if assignment.AccessType == 2:
            # these seem to be the old 'training' codes that don't show up any
            # more - most entries appear to have a value of '1'
            continue
        # TODO: handle leave time
        if assignment.IsLeaveTime == True:
            continue
        assignments[assignment.UniqueId] = Assignment(assignment)
    return assignments

# I really really tried to use the official API for this but it's astoundingly
# poorly designed (and documented). The mobile api is much friendlier.
def newentry(auth, mobauth, userid, assignment, date, numhours):
    numsecs = numhours * 60 * 60
    assert numsecs % 900 == 0
    assert numsecs == int(numsecs)
    numsecs = int(numsecs)

    timesheet = get_timesheet(auth, userid, weekstart(date))

    putval = {"KeyValues": [
        {"IsAttribute": True, "Property": "myproject", "Value": assignment.project_id},
        {"IsAttribute": True, "Property": "task", "Value": assignment.task_id},
        {"IsAttribute": True, "Property": "etc", "Value": None},
        {"IsAttribute": True, "Property": "charge", "Value": "0"},
        {"IsAttribute": False, "Property": "EntryDate", "Value": date.strftime('%m/%d/%Y')},
        {"IsAttribute": False, "Property": "RegularTime", "Value": numsecs},
        {"IsAttribute": False, "Property": "Overtime", "Value": 0},
        {"IsAttribute": False, "Property": "DoubleOvertime", "Value": 0},
        {"IsAttribute": False, "Property": "UniqueId", "Value": -1},
    ]}

    url = MOBAPI + 'Timesheets/%s?property=timeentrylite' % (timesheet.uid,)
    headers = {
        'API-Key': mobauth,
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = '=' + urllib.quote(json.dumps(putval))
    resp = requests.put(url, data=data, headers=headers)
    assert resp.status_code == 200

def makeweek(timesheet, assignments):
    week = OrderedDict()
    for i in range(7):
        week[timesheet.startdate + DT.timedelta(days=i)] = []
    for entry in timesheet.entries.values():
        assignment = assignments[entry.assignment_id]
        week[entry.date].append({
            "assignment": assignment.project_name + ' : ' + assignment.task_name,
            "numhours": entry.time.total_seconds()/60/60,
        })
    return week

def main():
    userid, auth, mobauth = init()

    # Get a monday
    startdate = DT.date(year=2015, month=05, day=23)
    weekdate = weekstart(startdate)

    # Actually get timesheet
    timesheet = get_timesheet(auth, userid, weekdate)
    assignments = get_assignments(auth, userid, weekdate)

    log('===================')
    log('Possible assignments:')
    for assignment in assignments.values():
        log('%s  -  %s', assignment.project_name, assignment.task_name)
    log('===================')
    log('Timesheets:')
    for date, entries in makeweek(timesheet, assignments).items():
        log('%s %s:', date.isoformat(), date.strftime('%a'))
        for entry in entries:
            log('    %s - %s hrs', entry['assignment'], entry['numhours'])
    log('===================')

if __name__ == '__main__':
    try:
        main()
    except:
        if DEBUG:
            import pdb
            pdb.post_mortem()
        else:
            raise
