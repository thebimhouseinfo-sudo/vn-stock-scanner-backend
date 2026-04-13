# Find this section (around line 15):
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ← Change this
    ...
)

# Change to:
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://vn-stock-scanner-frontend.vercel.app"  # ← Add your Vercel URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
