ซอร์สโค้ดแอปพลิเคชัน

const axios = require('axios');
const dbHost = '
localhost
';
const apiKey = '
sk_example_fake_cf8804ff0600342995229960
';
async function fetchCustomer(id) {
  return axios.get(`https://api.example.org/v1/customers/${id}`, { headers: { Authorization: apiKey } });
}
