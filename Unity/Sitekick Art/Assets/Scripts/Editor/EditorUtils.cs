using UnityEditor;

namespace Sitekick
{
	public static class EditorUtils
	{
		[MenuItem( "Assets/Mark Dirty", false, 9000 )]
		public static void MarkDirty()
		{
			foreach ( var obj in Selection.objects )
			{
				EditorUtility.SetDirty( obj );
			}
		}
	}
}
