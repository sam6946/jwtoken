/** Champs et normalisation du téléphone partagés par les parcours auth. */
export const countryCallingCodes = [
  { code: '237', label: '🇨🇲 +237' }, { code: '225', label: '🇨🇮 +225' },
  { code: '221', label: '🇸🇳 +221' }, { code: '241', label: '🇬🇦 +241' },
  { code: '242', label: '🇨🇬 +242' }, { code: '234', label: '🇳🇬 +234' },
  { code: '27', label: '🇿🇦 +27' }, { code: '33', label: '🇫🇷 +33' },
  { code: '32', label: '🇧🇪 +32' }, { code: '49', label: '🇩🇪 +49' },
  { code: '34', label: '🇪🇸 +34' }, { code: '39', label: '🇮🇹 +39' },
  { code: '44', label: '🇬🇧 +44' }, { code: '1', label: '🇺🇸/🇨🇦 +1' },
  { code: '971', label: '🇦🇪 +971' },
];

export function normalizePhoneInput(value: string): string {
  return value.replace(/\D/g, '').slice(0, 12);
}

export function isValidPhoneNumber(value: string, dialingCode: string): boolean {
  if (dialingCode === '237') return /^[2368]\d{8}$/.test(value);
  return value.length + dialingCode.length >= 8
    && value.length + dialingCode.length <= 15
    && /^[1-9]\d*$/.test(value.replace(/^0+/, ''));
}

export function phoneForApi(value: string, dialingCode: string): string {
  const localNumber = normalizePhoneInput(value);
  const significantNumber = dialingCode === '237' ? localNumber : localNumber.replace(/^0+/, '');
  return `+${dialingCode}${significantNumber}`;
}

interface PhoneNumberInputProps {
  value: string;
  dialingCode: string;
  onValueChange: (value: string) => void;
  onDialingCodeChange: (code: string) => void;
}

export function PhoneNumberInput({ value, dialingCode, onValueChange, onDialingCodeChange }: PhoneNumberInputProps) {
  return <div className="phone-field auth-phone-field"><select className="phone-prefix phone-code-select" aria-label="Indicatif téléphonique" value={dialingCode} onChange={(event) => onDialingCodeChange(event.target.value)}>{countryCallingCodes.map(({ code, label }) => <option key={code} value={code}>{label}</option>)}</select><input aria-label="Numéro de téléphone sans indicatif" autoComplete="tel-national" inputMode="tel" value={value} onChange={(event) => onValueChange(normalizePhoneInput(event.target.value))} placeholder={dialingCode === '237' ? '6 XX XX XX XX' : 'Numéro sans indicatif'} maxLength={12} /></div>;
}


export function OtpInput({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <div className="otp-input-group"><label htmlFor="otp-code">Code à 6 chiffres</label><input id="otp-code" className="otp-code-input" autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]*" maxLength={6} value={value} onChange={(event) => onChange(event.target.value.replace(/\D/g, '').slice(0, 6))} onPaste={(event) => { const pasted = event.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6); if (pasted) { event.preventDefault(); onChange(pasted); } }} placeholder="••••••" aria-describedby="otp-helper" /><span id="otp-helper" className="sr-only">Saisissez ou collez les six chiffres du code de vérification.</span><span className="otp-boxes" aria-hidden="true">{Array.from({ length: 6 }, (_, index) => <i className={index < value.length ? 'otp-box-filled' : ''} key={index}>{value[index] ?? ''}</i>)}</span></div>;
}
