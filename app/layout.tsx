import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title:'Family Wall',description:'Your family week, local weather, and family moments.'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
