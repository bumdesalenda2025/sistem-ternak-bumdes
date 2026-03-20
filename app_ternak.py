import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import io
from datetime import datetime

# --- 1. KONFIGURASI HALAMAN ---
st.set_page_config(page_title="BUMDes Ternak Pintar", layout="wide")

# --- 2. FUNGSI KEAMANAN (LOGIN) ---
def check_password():
    def password_entered():
        if st.session_state["password"] == "admin_bumdes_2026": # Ganti Password di Sini
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.text_input("Masukkan Password Akses Pengurus", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if not check_password():
    st.stop()

# --- 3. KONEKSI GOOGLE SHEETS ---
# Pastikan URL Sheets sudah dimasukkan di Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    return conn.read(ttl="0")

df_existing = load_data()
df_existing = df_existing.dropna(how="all")

# --- 4. SIDEBAR: INPUT DATA HARIAN ---
st.sidebar.header("📥 Input Data Harian")
with st.sidebar.form("input_form"):
    tgl = st.date_input("Tanggal Transaksi")
    
    st.sidebar.markdown("### 🥚 Produksi")
    prod_butir = st.number_input("Hasil Panen (Butir)", min_value=0)
    prod_kg = st.number_input("Berat Panen (Kg)", min_value=0.0, step=0.1)
    
    st.sidebar.markdown("### 💰 Penjualan")
    kat_jual = st.selectbox("Kategori Penjualan", ["Eceran", "Grosir", "MBG", "Tidak Ada"])
    jual_kg = st.number_input("Berat Terjual (Kg)", min_value=0.0, step=0.1)
    harga_kg = st.number_input("Harga per Kg (Rp)", value=25000)
    pembeli = st.text_input("Nama Pembeli", value="Umum")
    status_bayar = st.selectbox("Status Pembayaran", ["Lunas", "Belum Lunas (Hutang)"])
    
    st.sidebar.markdown("### 📦 Pakan & Biaya")
    pakan_pakai = st.number_input("Pakan Digunakan (Kg)", min_value=0.0, step=1.0)
    pakan_masuk = st.number_input("Pakan Masuk/Beli (Karung)", min_value=0)
    kat_biaya = st.selectbox("Kategori Biaya", ["Pakan", "Obat/Vaksin", "Gaji", "Listrik/Air", "Lainnya", "Nihil"])
    nom_biaya = st.number_input("Nominal Biaya (Rp)", value=0)
    
    submit = st.form_submit_button("Simpan Data Ke Sheets")

if submit:
    bln_thn = tgl.strftime("%B %Y")
    total_jual = jual_kg * harga_kg
    
    new_data = pd.DataFrame([{
        "Tanggal": str(tgl),
        "Bulan": bln_thn,
        "Produksi_Butir": prod_butir,
        "Produksi_Kg": prod_kg,
        "Terjual_Kg": jual_kg,
        "Harga_Per_Kg": harga_kg,
        "Total_Penjualan": total_jual,
        "Kategori_Jual": kat_jual,
        "Nama_Pembeli": pembeli,
        "Status_Bayar": status_bayar,
        "Kategori_Biaya": kat_biaya,
        "Total_Pengeluaran": nom_biaya,
        "Pakan_Masuk_Karung": pakan_masuk,
        "Pakan_Pakai_Karung": pakan_pakai / 50 if pakan_pakai > 0 else 0, # Konversi ke karung untuk stok
        "Berat_Pakan_Kg": pakan_pakai
    }])
    
    df_updated = pd.concat([df_existing, new_data], ignore_index=True)
    conn.update(data=df_updated)
    st.sidebar.success("✅ Data Berhasil Terkirim!")
    st.rerun()

# --- 5. DASHBOARD UTAMA (REAL-TIME) ---
st.title("🏛️ Dashboard Digital BUMDes Peternakan")

if not df_existing.empty:
    # --- METRIK UTAMA (KPI) ---
    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    
    sisa_pakan = df_existing["Pakan_Masuk_Karung"].sum() - df_existing["Pakan_Pakai_Karung"].sum()
    piutang = df_existing[df_existing["Status_Bayar"] == "Belum Lunas (Hutang)"]["Total_Penjualan"].sum()
    laba_riil = df_existing[df_existing["Status_Bayar"] == "Lunas"]["Total_Penjualan"].sum() - df_existing["Total_Pengeluaran"].sum()
    
    c1.metric("Sisa Stok Pakan", f"{sisa_pakan:.1f} Karung")
    c2.metric("Total Piutang", f"Rp {piutang:,.0f}")
    c3.metric("Laba Bersih Riil", f"Rp {laba_riil:,.0f}")
    
    # Hitung FCR Rata-rata
    total_pakan = df_existing["Berat_Pakan_Kg"].sum()
    total_telur = df_existing["Produksi_Kg"].sum()
    fcr = total_pakan / total_telur if total_telur > 0 else 0
    c4.metric("Efisiensi (FCR)", f"{fcr:.2f}")

    # --- LAPORAN PERIODE ---
    st.divider()
    st.header("📂 Laporan Akuntabilitas")
    mode_lap = st.radio("Pilih Periode:", ["Bulanan", "Semesteran", "Tahunan"], horizontal=True)
    
    if mode_lap == "Bulanan":
        pilihan = st.selectbox("Pilih Bulan", df_existing["Bulan"].unique())
        df_filtered = df_existing[df_existing["Bulan"] == pilihan]
    else:
        df_filtered = df_existing # Untuk simulasi sederhana
        pilihan = "Tahun Berjalan"

    # Rekap Kategori Jual
    st.subheader(f"Rincian Penjualan - {pilihan}")
    rekap_kat = df_filtered.groupby("Kategori_Jual").agg({
        "Terjual_Kg": "sum",
        "Total_Penjualan": "sum"
    }).rename(columns={"Terjual_Kg": "Total Kg", "Total_Penjualan": "Omzet (Rp)"})
    st.table(rekap_kat)

    # --- FUNGSI CETAK PDF ---
    class PDF(FPDF):
        def header(self):
            try: self.image('logo_bumdes.png', 10, 8, 25)
            except: pass
            self.set_font('Arial', 'B', 14)
            self.cell(30)
            self.cell(0, 10, 'BUMDes UNIT PETERNAKAN AYAM PETELUR', ln=True)
            self.ln(15)

    def export_pdf(df, judul, periode):
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, f"LAPORAN {judul.upper()}", ln=True, align='C')
        pdf.set_font("Arial", '', 12)
        pdf.cell(0, 10, f"Periode: {periode}", ln=True, align='C')
        pdf.ln(10)
        
        # Tabel Ringkasan
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(60, 10, "Kategori", 1)
        pdf.cell(60, 10, "Total Kg", 1)
        pdf.cell(70, 10, "Total Omzet", 1, ln=True)
        
        pdf.set_font("Arial", '', 11)
        rekap = df.groupby("Kategori_Jual").agg({"Terjual_Kg":"sum", "Total_Penjualan":"sum"})
        for k, r in rekap.iterrows():
            pdf.cell(60, 10, str(k), 1)
            pdf.cell(60, 10, f"{r['Terjual_Kg']:.1f}", 1)
            pdf.cell(70, 10, f"Rp {r['Total_Penjualan']:,.0f}", 1, ln=True)
            
        return pdf.output(dest='S').encode('latin-1')

    st.download_button(
        label="🖨️ Download Laporan PDF Resmi",
        data=export_pdf(df_filtered, mode_lap, pilihan),
        file_name=f"Laporan_{pilihan}.pdf",
        mime="application/pdf"
    )

    # Tabel Detail untuk Sekretaris
    with st.expander("Lihat Detail Transaksi Harian"):
        st.dataframe(df_filtered)

else:
    st.info("Belum ada data. Silakan Manajer Unit melakukan input melalui sidebar.")			
			
			
