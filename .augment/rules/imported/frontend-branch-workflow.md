---
type: "agent_requested"
---

### Frontend Development Workflow

This document outlines the development workflow and best practices for frontend development in the Construction Specification Assistant project.

## Branch Strategy

- **Feature Branches**: Create feature branches from `main` for new frontend features
  - Naming convention: `feature/frontend-<feature-name>`
  - Example: `feature/frontend-document-upload`, `feature/frontend-comparison-view`

- **Bug Fixes**: Create bug fix branches from `main`
  - Naming convention: `fix/frontend-<bug-description>`
  - Example: `fix/frontend-upload-validation`

## Development Guidelines

### Code Organization

1. **Component Structure**
   - Place reusable components in `frontend/src/components/`
   - Place page-level components in `frontend/src/pages/`
   - Place utility functions in `frontend/src/utils/`
   - Place API service functions in `frontend/src/services/`
   - Place type definitions in `frontend/src/types/`

2. **File Naming**
   - Use PascalCase for component files: `DocumentUpload.tsx`
   - Use camelCase for utility files: `apiClient.ts`
   - Use kebab-case for CSS/style files: `document-upload.css`

3. **Component Guidelines**
   - Keep components focused and single-purpose
   - Extract reusable logic into custom hooks
   - Use TypeScript interfaces for props
   - Document complex components with JSDoc comments

### State Management

- Use React hooks (useState, useEffect, useContext) for local state
- Consider using Context API for shared state across components
- For complex state, consider adding a state management library (e.g., Zustand, Redux Toolkit)

### API Integration

- Centralize API calls in `frontend/src/services/api.ts`
- Use async/await for API calls
- Implement proper error handling and loading states
- Use TypeScript interfaces for API request/response types

### Styling

- Use Tailwind CSS utility classes for styling
- Follow mobile-first responsive design principles
- Ensure proper contrast and accessibility
- Use consistent spacing and color schemes

### Testing

- Write unit tests for utility functions
- Write integration tests for complex components
- Test API service functions with mocked responses
- Ensure accessibility with automated testing tools

## Commit Guidelines

- Write clear, descriptive commit messages
- Use conventional commit format:
  - `feat(frontend): add document upload component`
  - `fix(frontend): resolve file validation issue`
  - `style(frontend): improve comparison results layout`
  - `refactor(frontend): extract API client logic`
  - `test(frontend): add tests for document upload`
  - `docs(frontend): update README with setup instructions`

## Pull Request Process

1. **Before Creating PR**
   - Ensure all tests pass
   - Run linter and fix any issues
   - Update documentation if needed
   - Test the feature thoroughly in the browser

2. **PR Description**
   - Describe what the PR does
   - Include screenshots for UI changes
   - List any breaking changes
   - Reference related issues or specs

3. **Code Review**
   - Address all review comments
   - Keep PRs focused and reasonably sized
   - Respond to feedback promptly

## Quality Checklist

Before committing frontend code, ensure:

- [ ] Code follows TypeScript best practices
- [ ] Components are properly typed
- [ ] No console.log statements in production code
- [ ] Proper error handling is implemented
- [ ] Loading states are shown for async operations
- [ ] UI is responsive and works on mobile devices
- [ ] Accessibility standards are met (ARIA labels, keyboard navigation)
- [ ] Code is formatted with Prettier
- [ ] ESLint shows no errors or warnings
- [ ] All imports are used and organized

## Environment Setup

- Use `.env.local` for local environment variables
- Never commit sensitive information (API keys, secrets)
- Document required environment variables in `.env.example`

## Performance Considerations

- Lazy load components when appropriate
- Optimize images and assets
- Minimize bundle size
- Use React.memo for expensive components
- Implement proper pagination for large data sets

## Accessibility

- Use semantic HTML elements
- Provide alt text for images
- Ensure keyboard navigation works
- Use ARIA labels where needed
- Test with screen readers
- Maintain proper color contrast ratios

