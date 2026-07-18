import http from 'k6/http';


export const options = {
  vus: 8,
  duration: '1s',
};

function dummyUUIDv4() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

export default function () {
  const url = 'http://localhost:1488/billing/top-up';

  // PREPARATION:
  // generate user_id via http://127.0.0.1:1488/identity/register
  // generate seti_id via http://127.0.0.1:1488/service/generate/seti-id
  // link user_id with seti_id via http://127.0.0.1:1488/billing/bind/seti-id
  const payload = JSON.stringify({
    user_id: "019f6530-708d-7927-ba8d-c57be2d2fdb5",
    amount: 6700,
    idempotency_key: dummyUUIDv4(),  // UUIDv7 in production
  });
  // WHAT TO EXPECT:
  // [409] DBAPIError --> prevented "parallel" manipulation (so no weird consequences)
  // [201] --> sucksex

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  http.post(url, payload, params);
}
