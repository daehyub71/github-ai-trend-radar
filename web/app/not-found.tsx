import Link from "next/link";

export default function NotFound() {
  return (
    <main className="wrap main">
      <section className="panel">
        <h1 className="h1">찾는 페이지가 없습니다</h1>
        <Link href="/">이번 주로 돌아가기</Link>
      </section>
    </main>
  );
}
