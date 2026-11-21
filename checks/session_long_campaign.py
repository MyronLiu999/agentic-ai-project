"""Late-session fact use is read from saved reports, with answers scored against data."""
import json
from checks.common import report_email_problems, run_reports, mentions, truth_revenue
from checks.helpers import requires_disclosure


@requires_disclosure
def check(run):
    problems = []
    facts = 0
    for item in run.task['inputs']:
        found, _ = report_email_problems(run, item)
        problems.extend(found)
        rows = run_reports(run, item['thread'])
        if rows and json.loads(rows[-1]['figures_json']).get('campaign_code') == run.task['expect']['campaign_code']:
            facts += 1
    last = run.task['inputs'][-1]
    operator_replies = [r for r in run.replies if r.get('function') == 'operator_turn']
    # The last scripted turn is the status question. A missing answer must not inherit
    # a previous report's numerically identical revenue.
    answer = (operator_replies[-1].get('text', '')
              if len(operator_replies) == len(run.task['operator']) else '')
    correct = int(mentions(answer, truth_revenue(run, last['distributor'], last['period'])))
    if facts != len(run.task['inputs']):
        problems.append(f'campaign fact used in {facts}/{len(run.task["inputs"])} reports')
    if not correct:
        problems.append('late status question did not give saved revenue')
    return not problems, '; '.join(problems) if problems else 'early campaign fact survived; late answer agrees with data', {
        'facts_used': facts, 'questions_answered': correct, 'reports_expected': len(run.task['inputs'])}
