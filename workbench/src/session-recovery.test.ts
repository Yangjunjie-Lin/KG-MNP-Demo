import {afterEach,describe,expect,it,vi} from 'vitest';
import {api,setCsrf,requestKeys} from './api';

afterEach(()=>{vi.unstubAllGlobals();setCsrf('');});
describe('short-lived authentication recovery',()=>{
  it('pauses writes after 401 without replaying and preserves request identities',async()=>{
    const fetch=vi.fn().mockResolvedValueOnce({ok:false,status:401,json:async()=>({error:{code:'SESSION_EXPIRED'}})});
    vi.stubGlobal('fetch',fetch);setCsrf('synthetic-csrf');requestKeys.set('synthetic-action','stable-key');
    await expect(api('/projects/synthetic/state')).rejects.toMatchObject({status:401});
    await expect(api('/projects/synthetic/toolchain/task.execute',{method:'POST'})).rejects.toMatchObject({code:'SESSION_REAUTH_REQUIRED'});
    expect(fetch).toHaveBeenCalledTimes(1);
    setCsrf('new-csrf');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(requestKeys.get('synthetic-action')).toBe('stable-key');
  });
  it('does not convert permission revocation into an expired data version',async()=>{
    vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:403,json:async()=>({error:{code:'FORBIDDEN'}})}));
    await expect(api('/projects/synthetic/state')).rejects.toMatchObject({status:403,code:'FORBIDDEN'});
  });
});
