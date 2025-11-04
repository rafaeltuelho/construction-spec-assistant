# Construction Specification Assistant - Frontend

A modern web application for uploading, comparing, and analyzing construction specification documents against submittals.

## Technology Stack

- **Framework**: React 19.1.1 with TypeScript
- **Build Tool**: Vite 7.1.12
- **Styling**: Tailwind CSS 4.1.16
- **Routing**: React Router DOM 7.1.1
- **HTTP Client**: Native Fetch API

## Features

### 1. Document Upload
- Upload specification and submittal documents (PDF format)
- Drag-and-drop file upload support
- File validation (type and size limits)
- Real-time upload progress tracking

### 2. Document Processing
- Automatic document parsing and OCR
- Progress indicators for processing stages
- Automatic fact extraction from specification documents
- Status polling for async operations

### 3. Comparison Analysis
- Automated comparison between specification requirements and submittal evidence
- Three verdict types:
  - **Consistent**: Submittal meets specification requirements
  - **Inconsistent**: Submittal does not meet specification requirements
  - **Unclear**: Insufficient information to determine compliance

### 4. Interactive Results Review
- Tabbed interface to filter results by verdict
- Summary statistics dashboard
- Detailed comparison cards showing:
  - Specification requirement
  - Submittal evidence
  - AI reasoning and confidence score
  - Retrieved document chunks

### 5. User Annotations
- Three annotation types:
  - **Disregard**: Mark comparison as not relevant
  - **Confirmed**: Confirm AI verdict
  - **Add Note**: Add custom notes to comparisons
- Persistent annotation storage
- Batch save functionality

### 6. Report Generation (Placeholder)
- UI prepared for future PDF report generation
- Will include all comparisons and user annotations

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable UI components
│   │   ├── ComparisonResultCard.tsx
│   │   ├── DocumentUpload.tsx
│   │   └── ProcessingStatus.tsx
│   ├── pages/              # Page-level components
│   │   ├── UploadPage.tsx
│   │   └── ResultsPage.tsx
│   ├── services/           # API client services
│   │   └── api.ts
│   ├── types/              # TypeScript type definitions
│   │   └── api.ts
│   ├── App.tsx             # Main app component with routing
│   ├── index.css           # Global styles and Tailwind directives
│   └── main.tsx            # Application entry point
├── public/                 # Static assets
├── .env.example            # Environment variables template
├── .env.local              # Local environment variables
├── package.json            # Dependencies and scripts
├── tailwind.config.js      # Tailwind CSS configuration
├── tsconfig.json           # TypeScript configuration
└── vite.config.ts          # Vite build configuration
```

## Getting Started

### Prerequisites

- Node.js 20.19+ or 22.12+ (recommended)
- npm 10.8.2+
- Backend API running on `http://localhost:8000`

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment variables:
```bash
cp .env.example .env.local
```

Edit `.env.local` if your backend API is running on a different URL:
```
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### Development

Start the development server:
```bash
npm run dev
```

The application will be available at `http://localhost:5173`

### Build

Create a production build:
```bash
npm run build
```

Preview the production build:
```bash
npm run preview
```

## Usage Workflow

### Step 1: Upload Documents
1. Navigate to the home page
2. Upload a specification document (PDF)
3. Upload a submittal document (PDF)
4. Wait for both documents to be processed

### Step 2: Start Comparison
1. Once both documents are processed, click "Start Comparison"
2. Wait for the comparison analysis to complete
3. You will be automatically redirected to the results page

### Step 3: Review Results
1. View summary statistics at the top of the page
2. Use tabs to filter results by verdict type
3. Review each comparison card:
   - Read the specification requirement
   - Review the submittal evidence
   - Understand the AI reasoning

### Step 4: Add Annotations
1. For each comparison, you can:
   - Click "Disregard" to mark as not relevant
   - Click "Confirmed" to confirm the AI verdict
   - Click "Add Note" to add custom notes
2. Click "Save Annotations" to persist your changes

### Step 5: Generate Report (Coming Soon)
- Report generation feature is planned for future release
- Will generate PDF reports with all comparisons and annotations


## API Integration

The frontend communicates with the backend API through the following endpoints:

- `POST /api/v1/documents/upload` - Upload documents
- `GET /api/v1/documents/{document_id}` - Get document status
- `POST /api/v1/facts/extract` - Trigger fact extraction
- `GET /api/v1/facts/extraction/{job_id}` - Get extraction status
- `POST /api/v1/comparison/compare-document` - Start comparison
- `GET /api/v1/comparison/compare-document/{job_id}` - Get comparison results
- `POST /api/v1/comparison/{job_id}/annotations` - Save user annotations

See `specs/08-frontend-integration.md` for detailed API specifications.

## Design Decisions

### Async Operations
- All long-running operations (document processing, fact extraction, comparison) use polling
- Status updates every 2 seconds
- Progress indicators show percentage and current stage
- Automatic transition to next step when operations complete

### State Management
- Local component state using React hooks
- No global state management library (Redux, Zustand) needed for current scope
- Annotations stored in Map for efficient lookups and updates

### Error Handling
- API errors displayed in user-friendly error messages
- Failed operations show error state with retry options
- Form validation prevents invalid file uploads

### Styling Approach
- Tailwind CSS utility classes for rapid development
- Custom component classes defined in `index.css`
- Consistent color scheme using primary blue palette
- Responsive design for mobile and desktop

### Type Safety
- Comprehensive TypeScript types for all API requests/responses
- Strict type checking enabled
- Type inference for better developer experience

## Assumptions

1. **Backend API**: Assumes backend API is running and accessible at configured URL
2. **CORS**: Assumes backend has CORS configured for `http://localhost:5173`
3. **File Format**: Only PDF files are supported (as per backend requirements)
4. **File Size**: Maximum file size is 50MB (configurable in backend)
5. **Authentication**: No authentication/authorization implemented (future enhancement)
6. **Single Session**: No multi-user or session management (future enhancement)
7. **Browser Support**: Modern browsers with ES2020+ support
8. **Network**: Assumes stable network connection for polling operations

## Known Limitations

1. **Report Generation**: UI is prepared but backend implementation is placeholder
2. **Product Description**: Upload UI supports it but workflow focuses on spec vs submittal
3. **Pagination**: Results page loads all comparisons at once (may need pagination for large datasets)
4. **Offline Support**: No offline capabilities or service worker
5. **Real-time Updates**: Uses polling instead of WebSockets for status updates
6. **File Preview**: No PDF preview functionality
7. **Comparison History**: No persistence of previous comparison sessions

## Future Enhancements

- [ ] Implement report generation with PDF export
- [ ] Add product description document comparison workflow
- [ ] Implement pagination for large result sets
- [ ] Add document preview functionality
- [ ] Add comparison history and session management
- [ ] Implement user authentication and authorization
- [ ] Add WebSocket support for real-time updates
- [ ] Add export functionality (CSV, JSON)
- [ ] Implement advanced filtering and search
- [ ] Add dark mode support

## Troubleshooting

### Development Server Won't Start
- Check Node.js version: `node --version` (should be 20.19+ or 22.12+)
- Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
- Check port 5173 is not in use

### API Connection Errors
- Verify backend is running: `curl http://localhost:8000/health`
- Check `.env.local` has correct API URL
- Verify CORS is configured in backend

### Build Errors
- Run TypeScript check: `npm run tsc`
- Check for missing dependencies: `npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`

## Contributing

Follow the guidelines in `.augment/rules/imported/frontend-branch-workflow.md` for:
- Branch naming conventions
- Code organization standards
- Commit message format
- Quality checklist before PR submission

## License

[Add license information here]

