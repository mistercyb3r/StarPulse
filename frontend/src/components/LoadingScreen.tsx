import "./LoadingScreen.css";

export function LoadingScreen({ message }: { message: string }) {
  return (
    <div className="loading-screen">
      <p>{message}</p>
    </div>
  );
}
