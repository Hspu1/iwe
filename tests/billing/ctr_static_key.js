import http from 'k6/http';


export const options = {
  vus: 8,
  duration: '1s',
};

export default function () {
  const url = 'http://localhost:1488/billing/top-up';

  // PREPARATION:
  // generate user_id via http://127.0.0.1:1488/identity/register (ts also serves as an idempotency_key to simplify the flow)
  // generate seti_id via http://127.0.0.1:1488/service/generate/seti-id
  // link user_id with seti_id via http://127.0.0.1:1488/billing/bind/seti-id
  const payload = JSON.stringify({
    user_id: "019f6530-708d-7927-ba8d-c57be2d2fdb5",
    amount: 6700,
    idempotency_key: "019f6530-708d-7927-ba8d-c57be2d2fdb5",
  });
  // WHAT TO EXPECT:
  // first req [201], then
  // [409] DBAPIError --> prevented "parallel" manipulation (so no weird consequences)
  // [202] IntegrityError --> failed with UQ (exists alrdy)

  const params = {
    headers: { 'Content-Type': 'application/json' },
  };

  http.post(url, payload, params);
}
