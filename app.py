import firebase_admin
from firebase_admin import credentials, db, auth
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import datetime

app = Flask(__name__)
app.secret_key = 'AIzaSyCDwrHxMzicO0n1RisxwEme0JGnOrYeZwY' 

# ==========================================
# 0. KONFIGURASI FIREBASE
# ==========================================
if not firebase_admin._apps:
    # Pastikan path ini sesuai file json Anda
    cred = credentials.Certificate("firebase/serviceAccountKey.json")
    firebase_admin.initialize_app(cred, {
        'databaseURL': 'https://perpus-syahroni-default-rtdb.firebaseio.com/'
    })

ref_buku = db.reference('buku')
ref_users = db.reference('users')
# [BARU] Tambahkan referensi ke tabel peminjaman agar bisa dihitung
ref_peminjaman = db.reference('peminjaman')
ref_denda_member = db.reference('denda_member')

# --- KONFIGURASI ADMIN ---
DAFTAR_ADMIN = [
    "tinofebrianefendi@students.amikom.ac.id",
    "hasbi@students.amikom.ac.id",
    "alfebriosetianugraha@students.amikom.ac.id"
]

# ==========================================
# 1. AUTH & PUBLIC ROUTES
# ==========================================
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login')
def login():
    if 'user' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('dashboard'))
        else:
            return redirect(url_for('member_area'))
    return render_template('login.html')

@app.route('/register')
def register():
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/google_auth', methods=['POST'])
def google_auth():
    token_client = request.json.get('token')
    try:
        decoded_token = auth.verify_id_token(token_client)
        uid = decoded_token['uid']
        email = decoded_token['email']
        nama = decoded_token.get('name', email.split('@')[0])
        
        user_db = ref_users.child(uid).get()
        role = 'anggota' 
        
        if email in DAFTAR_ADMIN:
            role = 'admin'
            if user_db and user_db.get('role') != 'admin':
                ref_users.child(uid).update({'role': 'admin'})
        else:
            if user_db: role = user_db.get('role', 'anggota')
            else: role = 'anggota'
            
        if not user_db:
            ref_users.child(uid).set({
                'nama': nama, 'email': email, 'role': role,
                'join_at': str(datetime.datetime.now())
            })
            
        session['user'] = nama
        session['uid'] = uid
        session['role'] = role
        
        tujuan = url_for('dashboard') if role == 'admin' else url_for('member_area')
        return jsonify({'status': 'success', 'redirect_url': tujuan})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

# ==========================================
# 2. DASHBOARD ADMIN (LOGIKA DIPERBAIKI)
# ==========================================
@app.route('/dashboard')
def dashboard():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    # 1. Hitung Buku & Stok
    semua_buku = ref_buku.get()
    if semua_buku is None: semua_buku = {}
    
    total_judul = len(semua_buku)
    total_stok = sum(int(b.get('stok', 0)) for b in semua_buku.values())
    
    # 2. [PERBAIKAN] Hitung Peminjaman Aktif dari Database
    semua_pinjam = ref_peminjaman.get()
    total_pinjam_aktif = 0
    
    if semua_pinjam:
        # Hitung data yang statusnya 'Dipinjam'
        total_pinjam_aktif = sum(1 for p in semua_pinjam.values() if p.get('status') == 'Dipinjam')
    
    # 3. Kirim data ke HTML
    return render_template('index.html', 
                           nama_user=session['user'],
                           stats={
                               'judul': total_judul, 
                               'stok': total_stok, 
                               'anggota': 87,          # Anggota masih dummy
                               'pinjam': total_pinjam_aktif # Sekarang sudah Real-time!
                           })

# ==========================================
# 3. DATA BUKU ADMIN
# ==========================================
@app.route('/data_buku')
def data_buku():
    if session.get('role') != 'admin': return redirect(url_for('member_area'))
    semua_buku = ref_buku.get() or {}
    return render_template('data_buku.html', buku=semua_buku, nama_user=session['user'])

@app.route('/tambah', methods=['POST'])
def tambah_buku():
    if session.get('role') != 'admin': return redirect(url_for('member_area'))
    
    # --- TAMBAHKAN BARIS INI ---
    genre = request.form.get('genre') 
    judul = request.form['judul']
    penulis = request.form['penulis']
    stok = int(request.form['stok'])
    url_gambar = request.form.get('url_gambar') or "https://via.placeholder.com/150x200?text=No+Cover"

    # --- TAMBAHKAN 'genre': genre DI DALAM PUSH ---
    ref_buku.push({
        'judul': judul, 
        'penulis': penulis, 
        'genre': genre, # <--- Tambahkan ini
        'stok': stok, 
        'url_gambar': url_gambar
    })
    return redirect(url_for('data_buku'))

@app.route('/update/<id>', methods=['POST'])
def update_buku(id):
    if session.get('role') != 'admin': return redirect(url_for('member_area'))
    
    # --- TAMBAHKAN BARIS INI ---
    genre_baru = request.form.get('genre')
    
    url_baru = request.form.get('url_gambar') or "https://via.placeholder.com/150x200?text=No+Cover"
    
    # --- TAMBAHKAN 'genre': genre_baru DI DALAM UPDATE ---
    ref_buku.child(id).update({
        'judul': request.form['judul'],
        'penulis': request.form['penulis'],
        'genre': genre_baru, # <--- Tambahkan ini
        'stok': int(request.form['stok']),
        'url_gambar': url_baru
    })
    return redirect(url_for('data_buku'))

@app.route('/hapus/<id>')
def hapus_buku(id):
    if session.get('role') != 'admin': return redirect(url_for('member_area'))
    ref_buku.child(id).delete()
    return redirect(url_for('data_buku'))

# ==========================================
# 4. MEMBER AREA (DASHBOARD REAL)
# ==========================================
@app.route('/member')
def member_area():
    if 'user' not in session: return redirect(url_for('login'))
    
    uid = session['uid']
    
    # --- 1. DATA PEMINJAMAN ---
    semua_pinjam = ref_peminjaman.get() or {}
    pinjaman_saya = []
    
    for key, val in semua_pinjam.items():
        if val.get('uid') == uid:
            pinjaman_saya.append(val)
            
    aktif = sum(1 for x in pinjaman_saya if x['status'] == 'Dipinjam')
    history = sum(1 for x in pinjaman_saya if x['status'] in ['Dikembalikan', 'Selesai'])
    
    # --- 2. [BARU] DATA DENDA ---
    semua_denda = ref_denda_member.get() or {}
    total_denda_belum_bayar = 0
    
    for key, val in semua_denda.items():
        # Ambil denda milik user ini DAN statusnya 'belum'
        if val.get('uid') == uid and val.get('status') == 'belum':
            try:
                total_denda_belum_bayar += int(val.get('jumlah_denda', 0))
            except:
                pass
    
    # Format rupiah untuk tampilan (misal: 1.000.000)
    denda_fmt = "{:,}".format(total_denda_belum_bayar).replace(',', '.')

    return render_template('member.html', 
                           nama_user=session['user'], 
                           peminjaman=pinjaman_saya, 
                           stats={
                               'aktif': aktif, 
                               'history': history, 
                               'denda': total_denda_belum_bayar, # Integer (untuk logika IF)
                               'denda_fmt': denda_fmt            # String (untuk tampilan Rp)
                           })
# ==========================================
# 5. [PENTING] LOGIKA PROSES PINJAM BUKU
# ==========================================
@app.route('/pinjam/<buku_id>', methods=['POST'])
def pinjam_buku(buku_id):
    if 'user' not in session: return redirect(url_for('login'))
    
    # 1. Ambil Data Buku
    buku = ref_buku.child(buku_id).get()
    
    if buku and int(buku.get('stok', 0)) > 0:
        # 2. Kurangi Stok
        stok_baru = int(buku['stok']) - 1
        ref_buku.child(buku_id).update({'stok': stok_baru})
        
        # 3. Hitung Tanggal
        tgl_sekarang = datetime.datetime.now()
        tgl_kembali = tgl_sekarang + datetime.timedelta(days=7)
        
        # 4. Simpan ke Firebase 'peminjaman'
        data_pinjam = {
            'uid': session['uid'],
            'nama_peminjam': session['user'],
            'buku_id': buku_id,
            'judul': buku['judul'],
            'url_gambar': buku.get('url_gambar', ''),
            'tgl_pinjam': tgl_sekarang.strftime('%d-%m-%Y'),
            'tenggat': tgl_kembali.strftime('%d-%m-%Y'),
            'status': 'Dipinjam'
        }
        ref_peminjaman.push(data_pinjam)
        
    return redirect(url_for('member_area'))

# ==========================================
# 6. ROUTE LAINNYA
# ==========================================
@app.route('/katalog')
def katalog_buku():
    return redirect(url_for('daftar_buku_member'))

@app.route('/member/daftar-buku')
def daftar_buku_member():
    if 'user' not in session: return redirect(url_for('login'))
    data_buku = ref_buku.get() or {}
    return render_template('daftar_buku_member.html', buku=data_buku, nama_user=session.get('user'))

# ==========================================
#  ROUTE DENDA MEMBER
# ==========================================
@app.route('/member/denda')
def member_denda():
    if 'user' not in session: return redirect(url_for('login'))
    
    uid = session['uid']
    
    # 1. Ambil semua data denda dari Firebase
    semua_denda = ref_denda_member.get()
    
    # 2. Filter: Hanya ambil data milik user yang sedang login
    denda_user = {}
    if semua_denda:
        for key, val in semua_denda.items():
            if val.get('uid') == uid:
                denda_user[key] = val
    
    # 3. Hitung Statistik
    total_denda = 0
    belum_dibayar = 0
    sudah_dibayar = 0
    
    for key, val in denda_user.items():
        # Pastikan data angka aman
        try:
            nominal = int(val.get('jumlah_denda', 0))
        except:
            nominal = 0
            
        status = val.get('status', 'belum') # Default 'belum'
        
        total_denda += nominal
        
        if status == 'belum':
            belum_dibayar += nominal
        else:
            sudah_dibayar += nominal
            
    jumlah_denda = len(denda_user)
    
    # Fungsi format rupiah sederhana (misal: 50000 jadi 50.000)
    def format_idr(nilai):
        return "{:,}".format(nilai).replace(',', '.')

    return render_template('member_denda.html', 
                           denda_data=denda_user,
                           total_denda=format_idr(total_denda),
                           belum_dibayar=format_idr(belum_dibayar),
                           sudah_dibayar=format_idr(sudah_dibayar),
                           jumlah_denda=jumlah_denda,
                           nama_user=session['user'])

@app.route('/me')
def member_history():
    if 'user' not in session: return redirect(url_for('login'))
    return redirect(url_for('member_area'))

# ==========================================
# 8. FITUR PENGEMBALIAN BUKU (ADMIN)
# ==========================================

# A. Halaman Kelola Peminjaman (Admin View)
@app.route('/admin/peminjaman')
def admin_peminjaman():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Ambil semua data peminjaman
    semua_pinjam = ref_peminjaman.get()
    if semua_pinjam is None: semua_pinjam = {}
    
    return render_template('peminjaman_admin.html', 
                           peminjaman=semua_pinjam, 
                           nama_user=session['user'])

# B. Proses Pengembalian (Update Status & Stok)
@app.route('/admin/kembali/<id>', methods=['POST'])
def proses_kembali(id):
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # 1. Ambil data transaksi berdasarkan ID
    transaksi = ref_peminjaman.child(id).get()
    
    if transaksi and transaksi.get('status') == 'Dipinjam':
        # 2. Update Status Transaksi menjadi 'Dikembalikan'
        tgl_kembali_real = datetime.datetime.now().strftime('%d-%m-%Y')
        
        ref_peminjaman.child(id).update({
            'status': 'Dikembalikan',
            'tgl_kembali_real': tgl_kembali_real
        })
        
        # 3. KEMBALIKAN STOK BUKU (+1)
        buku_id = transaksi.get('buku_id')
        if buku_id:
            data_buku = ref_buku.child(buku_id).get()
            if data_buku:
                stok_sekarang = int(data_buku.get('stok', 0))
                stok_baru = stok_sekarang + 1
                
                # Update stok di database buku
                ref_buku.child(buku_id).update({'stok': stok_baru})
            
    return redirect(url_for('admin_peminjaman'))

# ==========================================
# 9. FITUR KELOLA DENDA (ADMIN) - PERBAIKAN
# ==========================================

# A. Halaman Kelola Denda (Admin View)
@app.route('/admin/denda')
def admin_denda_page():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    # 1. Ambil Data Denda & Users
    semua_denda = ref_denda_member.get() or {}
    semua_users = ref_users.get() or {} # Diperlukan untuk dropdown nama member
    
    # 2. Hitung Statistik Admin (Total Semua Member)
    total_denda = 0
    belum_dibayar = 0
    sudah_dibayar = 0
    
    for key, val in semua_denda.items():
        try:
            nominal = int(val.get('jumlah_denda', 0))
        except:
            nominal = 0
        
        status = val.get('status', 'belum')
        total_denda += nominal
        
        if status == 'belum':
            belum_dibayar += nominal
        else:
            sudah_dibayar += nominal
            
    # Format Rupiah Helper
    def format_idr(nilai):
        return "{:,}".format(nilai).replace(',', '.')

    # PERHATIKAN: Render ke 'denda_admin.html' yang baru dibuat
    return render_template('denda_admin.html', 
                           denda_data=semua_denda,
                           users=semua_users,
                           total_denda=format_idr(total_denda),
                           belum_dibayar=format_idr(belum_dibayar),
                           sudah_dibayar=format_idr(sudah_dibayar),
                           jumlah_transaksi=len(semua_denda),
                           nama_user=session['user'])

# B. Proses Tambah Denda (Manual/Test)
@app.route('/admin/denda/tambah', methods=['POST'])
def tambah_denda_admin():
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    uid_member = request.form['uid']
    judul_buku = request.form['judul_buku']
    jumlah = int(request.form['jumlah_denda'])
    hari = request.form['keterlambatan']
    ket = request.form['keterangan']
    tanggal = datetime.datetime.now().strftime('%d-%m-%Y')
    
    data_baru = {
        'uid': uid_member,
        'judul_buku': judul_buku,
        'jumlah_denda': jumlah,
        'keterlambatan': hari,
        'tanggal_denda': tanggal,
        'status': 'belum',
        'keterangan': ket
    }
    
    ref_denda_member.push(data_baru)
    return redirect(url_for('admin_denda_page'))

# C. Proses Tandai Lunas
@app.route('/admin/denda/lunas/<id>')
def lunas_denda(id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    ref_denda_member.child(id).update({'status': 'lunas'})
    return redirect(url_for('admin_denda_page'))

# D. Proses Hapus Denda
@app.route('/admin/denda/hapus/<id>')
def hapus_denda(id):
    if session.get('role') != 'admin': return redirect(url_for('login'))
    
    ref_denda_member.child(id).delete()
    return redirect(url_for('admin_denda_page'))

if __name__ == '__main__':
    app.run(debug=True)