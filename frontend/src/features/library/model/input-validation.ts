/** Constraints from backend app/common/types.py. */
export function isValidCardLanguage(value: string): boolean {
  return /^[A-Za-z]{2,3}$/.test(value.trim());
}

export function isValidDeckTitle(value: string): boolean {
  const title = value.trim();
  const length = [...title].length;
  return length >= 3 && length <= 50 && !/[\t\n\r\v\f\x85\u2028\u2029]/.test(title);
}
