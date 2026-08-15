import axios from 'axios';

export async function fetchLatestGarment() {
  try {
    // කෙලින්ම සම්පූර්ණ URL එක මෙතන ලබා දී ඇත
    const response = await axios.get(
      'http://127.0.0.1:8000/api/latest-garment',
      { timeout: 5000 }
    );
    return response.data;
  } catch (error: any) {
    console.error("Backend Connection Error:", error.message);
    return null;
  }
}