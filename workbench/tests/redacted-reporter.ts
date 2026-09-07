import type {Reporter,TestCase,TestError,TestResult} from '@playwright/test/reporter';

// Native request timeout logs can include Cookie/Authorization headers. Keep
// failure locations and assertions, but never export browser credentials.
function redact(error:TestError){
  for(const key of ['message','stack','snippet'] as const){
    if(error[key])error[key]=error[key]!
      .replace(/(^.*\b(?:cookie|authorization|x-csrf-token):)[^\r\n]*/gim,'$1 [REDACTED]')
      .replace(/kgmnp_session=[^\s;"']+/g,'kgmnp_session=[REDACTED]');
  }
}
export default class RedactedReporter implements Reporter{
  onTestEnd(_test:TestCase,result:TestResult){result.errors.forEach(redact);}
  onError(error:TestError){redact(error);}
}
