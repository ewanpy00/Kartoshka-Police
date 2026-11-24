export function defang(value: string): string {
  return value.replace(/^http(s?):\/\//i, 'hxxp$1://').replace(/\./g, '[.]')
}
