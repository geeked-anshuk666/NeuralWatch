"""
Module: compliance_score
Purpose: Standalone utility to query and print EU AI Act compliance report from Splunk indexes.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - splunk-sdk: to connect and query
  - python-dotenv: environment config

Usage:
  python splunk_app/bin/compliance_score.py
"""

import os
import json
import logging
from dotenv import load_dotenv
import splunklib.client as client
import splunklib.results as results

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neuralwatch_compliance")

def get_compliance_report() -> dict:
    """
    Executes the EU AI Act compliance score query in Splunk and returns a JSON report.
    """
    host = os.getenv("SPLUNK_HOST", "localhost")
    port = int(os.getenv("SPLUNK_PORT", "8089"))
    username = os.getenv("SPLUNK_USERNAME", "admin")
    password = os.getenv("SPLUNK_PASSWORD")
    
    if not password:
        return {"error": "Splunk credentials not set in environment."}
        
    try:
        service = client.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            verify=False
        )
        
        # Load the compliance query
        compliance_query = (
            '| inputlookup neuralwatch_compliance_baseline.csv '
            '| join type=left service [search index=neuralwatch_ai_calls earliest=-24h | stats count as total_calls, count(eval(status="error")) as errors by service] '
            '| join type=left service [search index=neuralwatch_injections earliest=-24h | stats count(eval(injection_score>0.65)) as injection_events by service] '
            '| eval art9_score=if(injection_events<5 OR isnull(injection_events), 100, max(0,100-injection_events*5)) '
            '| eval art13_score=if(disclosure_enabled=1,100,0) '
            '| eval art14_score=if(human_review_required=0,100, round(human_review_threshold*100,0)) '
            '| eval art17_score=if(isnull(errors) OR total_calls=0,100, round((1-errors/total_calls)*100,0)) '
            '| eval art72_score=90 '
            '| eval overall_score=round((art9_score+art13_score+art14_score+art17_score+art72_score)/5,1) '
            '| eval status=case(overall_score>=90,"COMPLIANT",overall_score>=70,"AT RISK",true(),"NON-COMPLIANT") '
            '| table service, overall_score, status, art9_score, art13_score, art14_score, art17_score, art72_score'
        )
        
        job = service.jobs.create(compliance_query)
        while not job.is_done():
            pass
            
        has_xml_reader = hasattr(results, "ResultsReader")
        output_mode = "xml" if has_xml_reader else "json"
        
        raw_results = job.results(count=100, output_mode=output_mode)
        if has_xml_reader:
            reader = getattr(results, "ResultsReader")(raw_results)
        else:
            reader = getattr(results, "JSONResultsReader")(raw_results)
            
        report_data = []
        for result in reader:
            if isinstance(result, dict):
                report_data.append(dict(result))
                
        return {
            "status": "success",
            "services": report_data,
            "overall_average": round(sum(float(s["overall_score"]) for s in report_data) / len(report_data), 1) if report_data else 0.0
        }
        
    except Exception as e:
        logger.error(f"[NeuralWatch] Compliance query error: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    report = get_compliance_report()
    print(json.dumps(report, indent=2))
