/**
 * Utility functions for string formatting and normalization
 */

/**
 * Normalize patient name to have proper capitalization:
 * First letter uppercase, rest lowercase for each part of the name.
 *
 * Handles formats like:
 * - "COSTANZO, ROBERT" -> "Costanzo, Robert"
 * - "john doe" -> "John Doe"
 * - "SMITH-JONES, MARY ANNE" -> "Smith-Jones, Mary Anne"
 *
 * @param name - The patient name to normalize
 * @returns Normalized name with proper capitalization
 */
export function normalizePatientName(name: string | null | undefined): string {
  if (!name || typeof name !== 'string') {
    return name || '';
  }

  // Split by comma first to handle "Last, First" format
  const parts = name.split(',');
  const normalizedParts = parts.map(part => {
    // Handle each part (could be first name, last name, etc.)
    const words = part.trim().split(/\s+/).map(word => {
      // Handle hyphenated names like "Smith-Jones"
      if (word.includes('-')) {
        return word
          .split('-')
          .map(segment => segment.charAt(0).toUpperCase() + segment.slice(1).toLowerCase())
          .join('-');
      }
      // Capitalize first letter, lowercase rest
      return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
    });
    return words.join(' ');
  });

  return normalizedParts.join(', ');
}
