-- Supabase Storage · photos 버킷 허용 규칙
-- Supabase → SQL Editor 에 통째로 붙여 넣고 Run.
-- 다시 실행해도 오류가 나지 않는다 (버킷은 없을 때만 만들고, 허용 규칙은 지웠다가 새로 만든다).
-- 올라온 그림 파일은 건드리지 않는다.

-- 1. photos 버킷 · 없을 때만 공개 버킷으로 만든다 (이미 있으면 설정을 바꾸지 않는다)
--    공개 버킷이어야 화면에서 그림 주소로 바로 보여 줄 수 있다
insert into storage.buckets (id, name, public)
values ('photos', 'photos', true)
on conflict (id) do nothing;

-- 2. 있던 허용 규칙 지우기 · 다시 실행할 때 「이미 있다」 오류가 나지 않게 한다
drop policy if exists "photos 올리기" on storage.objects;
drop policy if exists "photos 목록 보기" on storage.objects;

-- 3. 허용 규칙 · 로그인 없이 화면(anon 키)에서 photos 버킷에만 올리고 · 목록을 본다
create policy "photos 올리기" on storage.objects
  for insert to anon, authenticated
  with check (bucket_id = 'photos');

create policy "photos 목록 보기" on storage.objects
  for select to anon, authenticated
  using (bucket_id = 'photos');

-- 4. 확인 : 버킷 1줄 · 허용 규칙 2줄(INSERT, SELECT)이 보이면 성공
select 'bucket' as kind, id as name, case when public then '공개' else '비공개' end as detail
from storage.buckets
where id = 'photos'
union all
select 'policy', policyname, cmd || ' · ' || array_to_string(roles, ', ')
from pg_policies
where schemaname = 'storage'
  and tablename = 'objects'
  and policyname in ('photos 올리기', 'photos 목록 보기');
