export function BrandMark() {
  return (
    <svg className="brand-mark" viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <defs>
        <linearGradient id="garment-brand-background" x1="5" y1="3" x2="60" y2="63">
          <stop stopColor="#7189ff" />
          <stop offset="0.54" stopColor="#465fe2" />
          <stop offset="1" stopColor="#263997" />
        </linearGradient>
        <linearGradient id="garment-brand-badge" x1="42" y1="39" x2="59" y2="58">
          <stop stopColor="#50ebc3" />
          <stop offset="1" stopColor="#19b992" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="62" height="62" rx="19" fill="url(#garment-brand-background)" />
      <path
        d="M23 18.5h5c.5 2 1.9 3.1 4 3.1s3.5-1.1 4-3.1h5l8 7.5-5.4 6.4-4.3-3.2v20.2H24.7V29.2l-4.3 3.2-5.4-6.4 8-7.5Z"
        fill="#fff"
        fillOpacity="0.98"
      />
      <path d="M29 30.5h8M29 35.5h8" stroke="#788cff" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="47.2" cy="46.5" r="10.5" fill="url(#garment-brand-badge)" stroke="#344bbb" strokeWidth="2" />
      <path d="m42.7 46.5 3.1 3.1 6-6.2" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
