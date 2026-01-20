/**
 * Formats an ISO date string or date-time string to a human-readable format
 * @param dateString - ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
 * @returns Formatted date string (e.g., "January 15, 2024")
 */
export function formatDate(dateString: string | null | undefined): string {
  if (!dateString) {
    return 'N/A';
  }

  // Split on 'T' to get just the date part (YYYY-MM-DD)
  const datePart = dateString.split('T')[0];

  // Parse the date
  const [year, month, day] = datePart.split('-');

  if (!year || !month || !day) {
    return dateString; // Return original if parsing fails
  }

  // Month names
  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const monthIndex = parseInt(month, 10) - 1;
  const monthName = monthNames[monthIndex] || month;
  const dayNumber = parseInt(day, 10); // Remove leading zeros

  return `${monthName} ${dayNumber}, ${year}`;
}

/**
 * Formats a date to MM/DD/YYYY format
 * @param dateString - ISO date string (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS)
 * @returns Formatted date string (e.g., "01/15/2024")
 */
export function formatDateShort(dateString: string | null | undefined): string {
  if (!dateString) {
    return 'N/A';
  }

  // Split on 'T' to get just the date part (YYYY-MM-DD)
  const datePart = dateString.split('T')[0];

  // Parse the date
  const [year, month, day] = datePart.split('-');

  if (!year || !month || !day) {
    return dateString; // Return original if parsing fails
  }

  return `${month}/${day}/${year}`;
}
