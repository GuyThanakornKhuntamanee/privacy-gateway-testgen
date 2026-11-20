ซอร์สโค้ดแอปพลิเคชัน

const axios = require('axios');
const dbHost = '
localhost
';
const apiKey = '
process.env.API_KEY
';
async function fetchCustomer(id) {
  return axios.get(`https://api.example.org/v1/customers/${id}`, { headers: { Authorization: apiKey } });
}
# contact: thiraphat.lalita@example.org
