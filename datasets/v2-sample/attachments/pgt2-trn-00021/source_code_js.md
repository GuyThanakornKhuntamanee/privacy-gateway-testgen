## Application source

const axios = require('axios');
const dbHost = '
docs.example.org
';
const apiKey = '
<REDACTED>
';
async function fetchCustomer(id) {
  return axios.get(`https://api.example.org/v1/customers/${id}`, { headers: { Authorization: apiKey } });
}
